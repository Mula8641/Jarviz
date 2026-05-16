"""MiniMax Vision — describe screenshots using MiniMax-V01."""
import logging
import base64
from io import BytesIO
from typing import Optional

from config import config

log = logging.getLogger("vision")

def describe_screen(prompt: str = "Describe what you see on the screen in detail.") -> str:
    """Capture screen and send to MiniMax Vision for description."""
    from screen_capture import capture_screen
    png_bytes = capture_screen()
    if not png_bytes:
        return "Screen capture failed. Are you on Windows with pywin32 installed?"
    return describe_image_bytes(png_bytes, prompt)

def describe_image_bytes(image_bytes: bytes, prompt: str = "Describe what you see.") -> str:
    """Send raw image bytes to MiniMax Vision."""
    from llm import describe_image as llm_describe_image
    return llm_describe_image(image_bytes, prompt)

def describe_base64image(b64_data: str, prompt: str = "Describe what you see.") -> str:
    """From a base64-encoded image string."""
    from llm import describe_image as llm_describe_image
    import base64
    image_bytes = base64.b64decode(b64_data)
    return llm_describe_image(image_bytes, prompt)