"""Playwright browser automation — setup, launch, search, interact.

Uses a module-level pool so Chromium is launched once and reused across
requests, avoiding the 1–2 s startup cost per call.
"""
import logging
import threading
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False
    sync_playwright = None

from config import config
from errors import BrowserError, retry

log = logging.getLogger("browser")


class BrowserTools:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def launch(self, headless: bool = True):
        if not _HAS_PLAYWRIGHT:
            raise BrowserError("Playwright not installed.")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        self.page = self.context.new_page()
        log.info("Browser launched (headless=%s)", headless)
        return self

    def is_alive(self) -> bool:
        try:
            return bool(self.browser and self.browser.is_connected())
        except Exception:
            return False

    def open_url(self, url: str):
        if not self.page:
            raise BrowserError("Browser not launched")
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        log.info("Opened: %s", url)

    def search(self, query: str, engine: str = "https://www.google.com/search?q=") -> list:
        if not self.page:
            raise BrowserError("Browser not launched")
        search_url = f"{engine}{query.replace(' ', '+')}"
        self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        results = self.page.evaluate("""
            () => {
                const items = document.querySelectorAll('div.g');
                return Array.from(items).slice(0, 10).map(el => {
                    const title = el.querySelector('h3')?.innerText || '';
                    const snippet = el.querySelector('div[data-content-feature]')?.innerText
                        || el.querySelector('span')?.innerText || '';
                    return title + ' — ' + snippet;
                }).filter(t => t.length > 10);
            }
        """)
        log.info("Search '%s': %d results", query, len(results))
        return results

    def read_page(self, selector: Optional[str] = None) -> str:
        if not self.page:
            raise BrowserError("Browser not launched")
        if selector:
            el = self.page.locator(selector).first
            return el.inner_text() if el.count() > 0 else ""
        return self.page.content()

    def click(self, selector: str):
        if not self.page:
            raise BrowserError("Browser not launched")
        self.page.click(selector, timeout=10000)
        log.info("Clicked: %s", selector)

    def type_text(self, selector: str, text: str):
        if not self.page:
            raise BrowserError("Browser not launched")
        self.page.fill(selector, text)
        log.info("Typed into: %s", selector)

    def press(self, selector: str, key: str):
        if not self.page:
            raise BrowserError("Browser not launched")
        self.page.press(selector, key)

    def scroll(self, direction: str = "down", amount: int = 300):
        if not self.page:
            raise BrowserError("Browser not launched")
        delta = amount if direction == "down" else -amount
        self.page.evaluate(f"window.scrollBy(0, {delta})")

    def take_screenshot(self, path: Optional[str] = None) -> bytes:
        if not self.page:
            raise BrowserError("Browser not launched")
        return self.page.screenshot(path=path)

    def close(self):
        for attr in ("page", "context", "browser", "playwright"):
            obj = getattr(self, attr, None)
            if obj:
                try:
                    obj.close() if attr != "playwright" else obj.stop()
                except Exception:
                    pass
        log.info("Browser closed")


class _BrowserPool:
    """Singleton pool: one Chromium instance reused across all requests."""

    def __init__(self):
        self._bt: Optional[BrowserTools] = None
        self._lock = threading.Lock()

    def get(self) -> BrowserTools:
        with self._lock:
            if self._bt is None or not self._bt.is_alive():
                if self._bt:
                    try:
                        self._bt.close()
                    except Exception:
                        pass
                self._bt = BrowserTools()
                self._bt.launch(headless=True)
                log.info("Browser pool: new instance created")
            return self._bt

    def shutdown(self):
        with self._lock:
            if self._bt:
                self._bt.close()
                self._bt = None


_pool = _BrowserPool()


def get_browser() -> BrowserTools:
    """Return the shared pooled browser instance."""
    return _pool.get()


def shutdown_browser():
    """Call on app shutdown to clean up the pool."""
    _pool.shutdown()
