"""Windows screen capture using GDI+ / pywin32."""
import logging
from io import BytesIO
from typing import Optional

log = logging.getLogger("screen_capture")

def capture_screen(region: Optional[tuple[int, int, int, int]] = None) -> bytes:
    """
    Capture the screen or a region using Windows GDI+.
    region: (x, y, width, height) — if None, capture full screen.

    Returns PNG bytes.
    """
    try:
        import win32gui
        import win32ui
        import win32con
        import numpy as np
    except ImportError:
        log.error("pywin32 not installed. Run: pip install pywin32")
        return b""

    # Get screen dimensions
    screen_width = win32gui.GetSystemMetrics(win32con.SM_CXSCREEN)
    screen_height = win32gui.GetSystemMetrics(win32con.SM_CYSCREEN)

    if region:
        x, y, w, h = region
    else:
        x, y, w, h = 0, 0, screen_width, screen_height

    # Create device contexts
    desktop_dc = win32gui.GetDesktopWindow()
    window_dc = win32gui.GetWindowDC(desktop_dc)
    compat_dc = win32ui.CreateDCFromHandle(window_dc)

    # Create compatible bitmap
    mem_dc = compat_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(compat_dc, w, h)
    mem_dc.SelectObject(bitmap)

    # BitBlt — capture
    from ctypes import windll
    SRCCOPY = 0x00CC0020
    result = windll.gdi32.BitBlt(
        mem_dc.GetSafeHdc(),
        0, 0, w, h,
        window_dc,
        x, y,
        SRCCOPY
    )

    # Convert to PIL Image
    from PIL import Image
    bmpinfo = bitmap.GetInfo()
    bmpstr = bitmap.GetBitmapBits(True)
    img = Image.FromBuffer(
        "RGB",
        (w, h),
        bmpstr,
        "RGB",
        bmpinfo["bmWidth"] * 3,
        bmpinfo["bmWidth"]
    )

    # Convert to PNG bytes
    buf = BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    # Cleanup
    win32gui.DeleteObject(bitmap.GetHandle())
    mem_dc.DeleteDC()
    compat_dc.DeleteDC()
    win32gui.ReleaseDC(desktop_dc, window_dc)

    log.info("Screen captured: %dx%d, %d bytes", w, h, len(png_bytes))
    return png_bytes


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if sys.platform != "win32":
        print("Windows only")
        sys.exit(1)
    png = capture_screen()
    if png:
        with open("screenshot.png", "wb") as f:
            f.write(png)
        print("Screenshot saved to screenshot.png")