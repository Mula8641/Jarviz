"""ElevenLabs TTS — text → audio bytes using official SDK."""
import logging
from config import config

log = logging.getLogger("audio")

def text_to_speech(text: str) -> bytes:
    api_key = config.get("elevenlabs_api_key", "")
    voice_id = config.get("elevenlabs_voice_id", "")

    if not voice_id or not api_key:
        log.error("Missing ElevenLabs API key or voice ID")
        return b""

    try:
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=api_key)

        chunks = []
        for chunk in client.text_to_speech.stream(
            voice_id=voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_96",
        ):
            chunks.append(chunk)

        audio = b"".join(chunks)
        log.info("TTS generated %d bytes", len(audio))
        return audio

    except Exception as e:
        log.error("ElevenLabs error: %s", e)
        return b""