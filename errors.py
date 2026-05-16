"""Custom exceptions + retry helpers."""
import time
import logging

log = logging.getLogger("errors")

class VoiceAssistantError(Exception):
    """Base exception."""
    pass

class TTSServerError(VoiceAssistantError):
    """ElevenLabs TTS failed."""
    pass

class LLMError(VoiceAssistantError):
    """MiniMax LLM call failed."""
    pass

class BrowserError(VoiceAssistantError):
    """Playwright browser operation failed."""
    pass

class WakeError(VoiceAssistantError):
    """Wake trigger failed."""
    pass

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator: retry a function with exponential backoff."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_attempts:
                        wait = delay * (backoff ** (attempt - 1))
                        log.warning(
                            "Attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                            attempt, max_attempts, func.__name__, e, wait
                        )
                        time.sleep(wait)
                    else:
                        log.error("All %d attempts failed for %s", max_attempts, func.__name__)
            raise last_exc
        return wrapper
    return decorator