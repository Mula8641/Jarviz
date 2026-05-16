"""Temp screenshot cache — stores frames for vision analysis."""
import hashlib
import time
from pathlib import Path

_CACHE_DIR = Path(__file__).parent / ".screenshot_cache"
_CACHE_DIR.mkdir(exist_ok=True)

def storeScreenshot(image_bytes: bytes, label: str = "default") -> str:
    ts = int(time.time() * 1000)
    key = hashlib.md5(image_bytes[:1024]).hexdigest()[:8]
    filename = f"{label}_{ts}_{key}.png"
    path = _CACHE_DIR / filename
    path.write_bytes(image_bytes)
    return str(path)

def list_cached() -> list[Path]:
    return sorted(_CACHE_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)

def clear_cache(max_age_seconds: int = 3600):
    """Remove cached screenshots older than max_age_seconds."""
    now = time.time()
    removed = 0
    for p in list_cached():
        if now - p.stat().st_mtime > max_age_seconds:
            p.unlink()
            removed += 1
    return removed