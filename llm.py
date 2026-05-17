"""Multi-backend LLM — MiniMax → OpenAI → Anthropic → Ollama (first key wins)."""
import httpx
import logging
from config import config

log = logging.getLogger("llm")

MINIMAX_URL  = "https://api.minimax.io/v1"
OPENAI_URL   = "https://api.openai.com/v1"
ANTHROPIC_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _openai_chat(messages: list[dict], model: str, api_key: str, base_url: str = OPENAI_URL) -> str:
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{base_url}/chat/completions",
            json={"model": model, "messages": messages, "temperature": 0.7},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _anthropic_chat(messages: list[dict], model: str, api_key: str) -> str:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{ANTHROPIC_URL}/messages",
            json={"model": model, "max_tokens": 1024, "system": system, "messages": user_msgs},
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]


def _openai_tools(messages: list[dict], tools: list[dict], model: str, api_key: str,
                  base_url: str = OPENAI_URL) -> dict:
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{base_url}/chat/completions",
            json={"model": model, "messages": messages, "tools": tools,
                  "tool_choice": "auto", "temperature": 0.7},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        return {"tool_calls": calls, "content": msg.get("content") or ""} if calls \
               else {"content": msg.get("content", "")}


def _anthropic_tools(messages: list[dict], tools: list[dict], model: str, api_key: str) -> dict:
    """Translate OpenAI tool schema → Anthropic tool_use format and back."""
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]

    # Convert OpenAI tool schema → Anthropic schema
    ant_tools = [
        {
            "name": t["function"]["name"],
            "description": t["function"].get("description", ""),
            "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
        }
        for t in tools
    ]

    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{ANTHROPIC_URL}/messages",
            json={"model": model, "max_tokens": 1024, "system": system,
                  "messages": user_msgs, "tools": ant_tools},
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    content_blocks = data.get("content", [])
    text = next((b["text"] for b in content_blocks if b["type"] == "text"), "")

    # Translate Anthropic tool_use blocks → OpenAI tool_calls format
    tool_calls = []
    for b in content_blocks:
        if b["type"] == "tool_use":
            import json
            tool_calls.append({
                "id": b["id"],
                "type": "function",
                "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
            })

    return {"tool_calls": tool_calls, "content": text} if tool_calls else {"content": text}


# ── Public API ────────────────────────────────────────────────────────────────

def chat(messages: list[dict]) -> str:
    """Chat with the first available backend. Priority: MiniMax → OpenAI → Anthropic → Ollama."""

    if config.get("minimax_api_key"):
        try:
            return _openai_chat(messages, "MiniMax-M2.7",
                                config["minimax_api_key"], MINIMAX_URL)
        except Exception as e:
            log.warning("MiniMax error: %s", e)

    if config.get("openai_api_key"):
        try:
            model = config.get("openai_model", "gpt-4o")
            return _openai_chat(messages, model, config["openai_api_key"])
        except Exception as e:
            log.warning("OpenAI error: %s", e)

    if config.get("anthropic_api_key"):
        try:
            model = config.get("anthropic_model", "claude-sonnet-4-6")
            return _anthropic_chat(messages, model, config["anthropic_api_key"])
        except Exception as e:
            log.warning("Anthropic error: %s", e)

    ollama_url = config.get("ollama_base_url", "")
    if ollama_url:
        try:
            ollama_model = config.get("ollama_model", "llama3.2")
            with httpx.Client(timeout=90.0) as client:
                r = client.post(
                    f"{ollama_url}/api/chat",
                    json={"model": ollama_model, "messages": messages,
                          "stream": False, "options": {"temperature": 0.7}},
                )
                r.raise_for_status()
                return r.json().get("message", {}).get("content", "")
        except Exception as e:
            log.error("Ollama error: %s", e)

    return "Error: no LLM backend configured. Add an API key in Settings."


def chat_with_tools(messages: list[dict], tools: list[dict]) -> dict:
    """Chat with tools. Priority: MiniMax → OpenAI → Anthropic → Ollama → plain chat."""

    if config.get("minimax_api_key"):
        try:
            return _openai_tools(messages, tools, "MiniMax-M2.7",
                                 config["minimax_api_key"], MINIMAX_URL)
        except Exception as e:
            log.warning("MiniMax tool call error: %s", e)

    if config.get("openai_api_key"):
        try:
            model = config.get("openai_model", "gpt-4o")
            return _openai_tools(messages, tools, model, config["openai_api_key"])
        except Exception as e:
            log.warning("OpenAI tool call error: %s", e)

    if config.get("anthropic_api_key"):
        try:
            model = config.get("anthropic_model", "claude-sonnet-4-6")
            return _anthropic_tools(messages, tools, model, config["anthropic_api_key"])
        except Exception as e:
            log.warning("Anthropic tool call error: %s", e)

    ollama_url = config.get("ollama_base_url", "")
    if ollama_url:
        try:
            ollama_model = config.get("ollama_model", "llama3.2")
            with httpx.Client(timeout=90.0) as client:
                r = client.post(
                    f"{ollama_url}/api/chat",
                    json={"model": ollama_model, "messages": messages,
                          "tools": tools, "stream": False},
                )
                r.raise_for_status()
                msg = r.json().get("message", {})
                calls = msg.get("tool_calls") or []
                return {"tool_calls": calls, "content": msg.get("content") or ""} if calls \
                       else {"content": msg.get("content", "")}
        except Exception as e:
            log.warning("Ollama tool call error: %s", e)

    return {"content": chat(messages)}


def describe_image(image_bytes: bytes, prompt: str = "Describe what you see.") -> str:
    """Send screenshot to MiniMax Vision (or Claude if MiniMax key missing)."""
    import base64
    b64 = base64.b64encode(image_bytes).decode()

    if config.get("minimax_api_key"):
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(
                    f"{MINIMAX_URL}/chat/completions",
                    json={
                        "model": "MiniMax-V01",
                        "messages": [{"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                            {"type": "text", "text": prompt},
                        ]}],
                        "temperature": 0.5,
                    },
                    headers={"Authorization": f"Bearer {config['minimax_api_key']}",
                             "Content-Type": "application/json"},
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            log.warning("MiniMax vision error: %s", e)

    if config.get("anthropic_api_key"):
        try:
            model = config.get("anthropic_model", "claude-sonnet-4-6")
            with httpx.Client(timeout=60.0) as client:
                r = client.post(
                    f"{ANTHROPIC_URL}/messages",
                    json={
                        "model": model, "max_tokens": 1024,
                        "messages": [{"role": "user", "content": [
                            {"type": "image", "source": {
                                "type": "base64", "media_type": "image/png", "data": b64}},
                            {"type": "text", "text": prompt},
                        ]}],
                    },
                    headers={"x-api-key": config["anthropic_api_key"],
                             "anthropic-version": ANTHROPIC_VERSION,
                             "Content-Type": "application/json"},
                )
                r.raise_for_status()
                return r.json()["content"][0]["text"]
        except Exception as e:
            log.warning("Anthropic vision error: %s", e)

    if config.get("openai_api_key"):
        try:
            model = config.get("openai_model", "gpt-4o")
            with httpx.Client(timeout=60.0) as client:
                r = client.post(
                    f"{OPENAI_URL}/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                            {"type": "text", "text": prompt},
                        ]}],
                    },
                    headers={"Authorization": f"Bearer {config['openai_api_key']}",
                             "Content-Type": "application/json"},
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            log.warning("OpenAI vision error: %s", e)

    return "Error: no vision-capable backend configured."
