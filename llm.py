"""MiniMax LLM — chat + vision. Falls back to Ollama if MiniMax is unavailable."""
import httpx
import logging
from config import config

log = logging.getLogger("llm")

BASE_URL = "https://api.minimax.io/v1"


def _make_minimax_payload(messages: list[dict], model: str) -> dict:
    return {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
    }


def _make_ollama_payload(messages: list[dict], model: str) -> dict:
    return {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.7},
    }


def chat(messages: list[dict], model: str = "MiniMax-M2.7") -> str:
    api_key = config.get("minimax_api_key", "")

    # Try MiniMax first
    if api_key:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{BASE_URL}/chat/completions",
                    json=_make_minimax_payload(messages, model),
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            log.warning(
                "MiniMax HTTP %d — %s. Trying Ollama fallback.",
                e.response.status_code, e.response.text[:100],
            )
        except Exception as e:
            log.warning("MiniMax error: %s. Trying Ollama fallback.", e)

    # Fallback to Ollama
    ollama_url = config.get("ollama_base_url", "")
    ollama_model = config.get("ollama_model", "llama3.2")
    if not ollama_url:
        return "Error: MiniMax unavailable and Ollama not configured."

    try:
        with httpx.Client(timeout=90.0) as client:
            response = client.post(
                f"{ollama_url}/api/chat",
                json=_make_ollama_payload(messages, ollama_model),
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
    except httpx.HTTPStatusError as e:
        log.error("Ollama HTTP error: %s", e.response.text[:200])
        return f"Error: both MiniMax and Ollama failed. Last error: {e}"
    except Exception as e:
        log.error("Ollama error: %s", e)
        return f"Error: all LLM backends failed. Last error: {e}"


def describe_image(image_bytes: bytes, prompt: str = "Describe what you see.") -> str:
    """Send screenshot to MiniMax Vision for description."""
    api_key = config.get("minimax_api_key", "")
    if not api_key:
        log.error("MINIMAX_API_KEY not set")
        return "Error: API key not configured."

    import base64
    b64 = base64.b64encode(image_bytes).decode()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "MiniMax-V01",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0.5,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        log.error("MiniMax vision error: %s", e)
        return f"Error: {e}"