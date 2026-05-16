"""MiniMax LLM — chat + vision."""
import httpx
import logging
from config import config

log = logging.getLogger("llm")

BASE_URL = "https://api.minimax.chat/v1"

def chat(messages: list[dict], model: str = "MiniMax-Text-01") -> str:
    api_key = config.get("minimax_api_key", "")
    if not api_key:
        log.error("MINIMAX_API_KEY not set")
        return "Error: API key not configured."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
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
    except httpx.HTTPStatusError as e:
        log.error("MiniMax HTTP error: %s — %s", e.response.status_code, e.response.text)
        return f"Error: HTTP {e.response.status_code}"
    except Exception as e:
        log.error("MiniMax error: %s", e)
        return f"Error: {e}"


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