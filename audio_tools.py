"""ElevenLabs TTS — text → audio bytes."""
import httpx
import logging
from config import config

log = logging.getLogger("audio")

BASE_URL = "https://api.elevenlabs.io/v2"

def text_to_speech(text: str) -> bytes:
    voice_id = config.get("elevenlabs_voice_id", "")
    api_key = config.get("elevenlabs_api_key", "")

    if not voice_id or not api_key:
        log.error("Missing ElevenLabs API key or voice ID")
        return b""

    url = f"{BASE_URL}/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            log.info("TTS generated %d bytes", len(response.content))
            return response.content
    except httpx.HTTPStatusError as e:
        log.error("ElevenLabs HTTP error: %s — %s", e.response.status_code, e.response.text)
        return b""
    except Exception as e:
        log.error("ElevenLabs error: %s", e)
        return b""