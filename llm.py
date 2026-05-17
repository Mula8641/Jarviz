"""Multi-backend LLM — attempt-then-escalate routing.

Simple / short requests → MiniMax (cheap token plan).
Complex / heavy requests → capable backend (Anthropic or OpenAI).

Routing flow:
  1. Fast pre-check: if message is obviously heavy (>60 words or generation
     verb as first word) → skip MiniMax, go straight to capable backend.
  2. Otherwise try MiniMax. If response is weak (vague, too short, uncertain
     phrasing) → escalate to capable backend.
  3. Fallback chain: Ollama → error message.

Set routing_enabled=false in config to revert to the old priority chain.
"""
import json as _json
import httpx
import logging
from config import config

log = logging.getLogger("llm")

MINIMAX_URL       = "https://api.minimax.io/v1"
OPENAI_URL        = "https://api.openai.com/v1"
ANTHROPIC_URL     = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"

# Tracks the model that handled the most recent request (read by server.py)
last_used: str = ""

# Phrases that indicate the model hit its reasoning limit
_WEAK_PHRASES = frozenset({
    "i'm not sure", "i am not sure", "i don't have", "i do not have",
    "i cannot", "i can't", "unable to", "i lack", "i don't know",
    "i do not know", "no information", "not enough context",
    "insufficient information", "can't help", "cannot help",
    "beyond my", "outside my",
})

# First words that signal a generation / coding / heavy-analysis request
_SKIP_FIRST_WORDS = frozenset({
    "write", "generate", "code", "create", "build",
    "implement", "develop", "debug", "design", "draft",
})


# ── Weakness detector ─────────────────────────────────────────────────────────

def _response_is_weak(content: str) -> bool:
    """Return True if the response looks like the model gave up or bailed out."""
    if not content or len(content.strip()) < 10:
        return True
    lower = content.lower()
    return any(phrase in lower for phrase in _WEAK_PHRASES)


# ── Fast pre-check ────────────────────────────────────────────────────────────

def _should_skip_minimax(messages: list) -> bool:
    """Return True for obviously heavy requests — skip straight to capable model."""
    last = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
    )
    words = last.strip().split()
    if len(words) > 60:
        return True
    first = words[0].lower().rstrip(".,!?") if words else ""
    return first in _SKIP_FIRST_WORDS


# ── Low-level HTTP helpers ────────────────────────────────────────────────────

def _openai_chat(messages: list, model: str, api_key: str,
                 base_url: str = OPENAI_URL) -> str:
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{base_url}/chat/completions",
            json={"model": model, "messages": messages, "temperature": 0.7},
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _anthropic_chat(messages: list, model: str, api_key: str) -> str:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{ANTHROPIC_URL}/messages",
            json={"model": model, "max_tokens": 1024,
                  "system": system, "messages": user_msgs},
            headers={"x-api-key": api_key,
                     "anthropic-version": ANTHROPIC_VERSION,
                     "Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]


def _openai_tools(messages: list, tools: list, model: str, api_key: str,
                  base_url: str = OPENAI_URL) -> dict:
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{base_url}/chat/completions",
            json={"model": model, "messages": messages, "tools": tools,
                  "tool_choice": "auto", "temperature": 0.7},
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
        )
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        return {"tool_calls": calls, "content": msg.get("content") or ""} if calls \
               else {"content": msg.get("content", "")}


def _anthropic_tools(messages: list, tools: list, model: str, api_key: str) -> dict:
    """Translate OpenAI tool schema → Anthropic tool_use format and back."""
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]

    ant_tools = [
        {
            "name": t["function"]["name"],
            "description": t["function"].get("description", ""),
            "input_schema": t["function"].get("parameters",
                                              {"type": "object", "properties": {}}),
        }
        for t in tools
    ]

    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            f"{ANTHROPIC_URL}/messages",
            json={"model": model, "max_tokens": 1024, "system": system,
                  "messages": user_msgs, "tools": ant_tools},
            headers={"x-api-key": api_key,
                     "anthropic-version": ANTHROPIC_VERSION,
                     "Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    blocks = data.get("content", [])
    text = next((b["text"] for b in blocks if b["type"] == "text"), "")
    tool_calls = [
        {"id": b["id"], "type": "function",
         "function": {"name": b["name"], "arguments": _json.dumps(b["input"])}}
        for b in blocks if b["type"] == "tool_use"
    ]
    return {"tool_calls": tool_calls, "content": text} if tool_calls \
           else {"content": text}


# ── Capable-backend helpers ───────────────────────────────────────────────────

def _capable_name() -> str:
    """Human-readable label for the currently configured escalation backend."""
    target = config.get("escalation_backend", "anthropic")
    if target == "anthropic" and config.get("anthropic_api_key"):
        return f"Claude ({config.get('anthropic_model', 'claude-sonnet-4-6')})"
    if config.get("openai_api_key"):
        return f"GPT-4 ({config.get('openai_model', 'gpt-4o')})"
    if config.get("anthropic_api_key"):
        return f"Claude ({config.get('anthropic_model', 'claude-sonnet-4-6')})"
    return "Capable"


def _capable_chat(messages: list) -> str:
    target = config.get("escalation_backend", "anthropic")
    if target == "anthropic" and config.get("anthropic_api_key"):
        return _anthropic_chat(messages,
                               config.get("anthropic_model", "claude-sonnet-4-6"),
                               config["anthropic_api_key"])
    if config.get("openai_api_key"):
        return _openai_chat(messages,
                            config.get("openai_model", "gpt-4o"),
                            config["openai_api_key"])
    if config.get("anthropic_api_key"):
        return _anthropic_chat(messages,
                               config.get("anthropic_model", "claude-sonnet-4-6"),
                               config["anthropic_api_key"])
    raise RuntimeError("No capable backend configured")


def _capable_tools(messages: list, tools: list) -> dict:
    target = config.get("escalation_backend", "anthropic")
    if target == "anthropic" and config.get("anthropic_api_key"):
        return _anthropic_tools(messages, tools,
                                config.get("anthropic_model", "claude-sonnet-4-6"),
                                config["anthropic_api_key"])
    if config.get("openai_api_key"):
        return _openai_tools(messages, tools,
                             config.get("openai_model", "gpt-4o"),
                             config["openai_api_key"])
    if config.get("anthropic_api_key"):
        return _anthropic_tools(messages, tools,
                                config.get("anthropic_model", "claude-sonnet-4-6"),
                                config["anthropic_api_key"])
    raise RuntimeError("No capable backend configured")


# ── Legacy priority chain (routing_enabled=false) ─────────────────────────────

def _priority_chain(messages: list) -> str:
    global last_used
    if config.get("minimax_api_key"):
        try:
            r = _openai_chat(messages, "MiniMax-M2.7",
                             config["minimax_api_key"], MINIMAX_URL)
            last_used = "MiniMax"
            return r
        except Exception as e:
            log.warning("MiniMax error: %s", e)
    if config.get("openai_api_key"):
        try:
            model = config.get("openai_model", "gpt-4o")
            r = _openai_chat(messages, model, config["openai_api_key"])
            last_used = f"GPT-4 ({model})"
            return r
        except Exception as e:
            log.warning("OpenAI error: %s", e)
    if config.get("anthropic_api_key"):
        try:
            model = config.get("anthropic_model", "claude-sonnet-4-6")
            r = _anthropic_chat(messages, model, config["anthropic_api_key"])
            last_used = f"Claude ({model})"
            return r
        except Exception as e:
            log.warning("Anthropic error: %s", e)
    return _ollama_chat(messages)


def _ollama_chat(messages: list) -> str:
    global last_used
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
                last_used = f"Ollama ({ollama_model})"
                return r.json().get("message", {}).get("content", "")
        except Exception as e:
            log.error("Ollama error: %s", e)
    return "Error: no LLM backend configured. Add an API key in Settings."


# ── Public API ────────────────────────────────────────────────────────────────

def chat(messages: list) -> str:
    """Route to the right backend. Attempt MiniMax → escalate if weak."""
    global last_used

    if not config.get("routing_enabled", True):
        return _priority_chain(messages)

    skip_mm = _should_skip_minimax(messages)

    if skip_mm:
        log.info("Routing: heavy request detected → skipping MiniMax")
    elif config.get("minimax_api_key"):
        try:
            result = _openai_chat(messages, "MiniMax-M2.7",
                                  config["minimax_api_key"], MINIMAX_URL)
            if not _response_is_weak(result):
                last_used = "MiniMax"
                log.debug("Routing: MiniMax handled request")
                return result
            log.info("Routing: MiniMax response weak → escalating")
        except Exception as e:
            log.warning("Routing: MiniMax failed (%s) → escalating", e)

    # Escalate
    try:
        result = _capable_chat(messages)
        last_used = _capable_name()
        log.info("Routing: escalated to %s", last_used)
        return result
    except Exception as e:
        log.warning("Routing: capable backend failed (%s) → Ollama", e)

    return _ollama_chat(messages)


def chat_with_tools(messages: list, tools: list) -> dict:
    """Route tool-calling to the right backend."""
    global last_used

    if not config.get("routing_enabled", True):
        return _priority_chain_tools(messages, tools)

    skip_mm = _should_skip_minimax(messages)

    if skip_mm:
        log.info("Routing (tools): heavy request → skipping MiniMax")
    elif config.get("minimax_api_key"):
        try:
            result = _openai_tools(messages, tools, "MiniMax-M2.7",
                                   config["minimax_api_key"], MINIMAX_URL)
            # If MiniMax chose a tool it's working correctly — don't escalate
            if result.get("tool_calls"):
                last_used = "MiniMax"
                return result
            # No tool calls: check if the text answer is strong enough
            if not _response_is_weak(result.get("content", "")):
                last_used = "MiniMax"
                return result
            log.info("Routing (tools): MiniMax gave weak answer → escalating")
        except Exception as e:
            log.warning("Routing (tools): MiniMax failed (%s) → escalating", e)

    try:
        result = _capable_tools(messages, tools)
        last_used = _capable_name()
        log.info("Routing (tools): escalated to %s", last_used)
        return result
    except Exception as e:
        log.warning("Routing (tools): capable backend failed (%s)", e)

    # Ollama tool fallback
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
                last_used = f"Ollama ({ollama_model})"
                return {"tool_calls": calls, "content": msg.get("content") or ""} \
                       if calls else {"content": msg.get("content", "")}
        except Exception as e:
            log.warning("Ollama tool call error: %s", e)

    return {"content": chat(messages)}


def _priority_chain_tools(messages: list, tools: list) -> dict:
    """Legacy tool routing — first key wins."""
    global last_used
    if config.get("minimax_api_key"):
        try:
            r = _openai_tools(messages, tools, "MiniMax-M2.7",
                              config["minimax_api_key"], MINIMAX_URL)
            last_used = "MiniMax"
            return r
        except Exception as e:
            log.warning("MiniMax tool error: %s", e)
    if config.get("openai_api_key"):
        try:
            model = config.get("openai_model", "gpt-4o")
            r = _openai_tools(messages, tools, model, config["openai_api_key"])
            last_used = f"GPT-4 ({model})"
            return r
        except Exception as e:
            log.warning("OpenAI tool error: %s", e)
    if config.get("anthropic_api_key"):
        try:
            model = config.get("anthropic_model", "claude-sonnet-4-6")
            r = _anthropic_tools(messages, tools, model, config["anthropic_api_key"])
            last_used = f"Claude ({model})"
            return r
        except Exception as e:
            log.warning("Anthropic tool error: %s", e)
    return {"content": chat(messages)}


def describe_image(image_bytes: bytes, prompt: str = "Describe what you see.") -> str:
    """Send screenshot to MiniMax Vision (or Claude/GPT if MiniMax key missing)."""
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
                            {"type": "image_url",
                             "image_url": {"url": f"data:image/png;base64,{b64}"}},
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
                                "type": "base64", "media_type": "image/png",
                                "data": b64}},
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
                            {"type": "image_url",
                             "image_url": {"url": f"data:image/png;base64,{b64}"}},
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
