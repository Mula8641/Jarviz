"""Playwright browser automation — setup, launch, search, interact."""
import asyncio
import logging
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
except ImportError:
    sync_playwright = None

from config import config
from errors import BrowserError, retry

log = logging.getLogger("browser")

_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None

class BrowserTools:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def launch(self, headless: bool = True):
        """Launch Chromium browser."""
        if sync_playwright is None:
            raise BrowserError("Playwright not installed. Run: pip install playwright && playwright install chromium")

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.page = self.context.new_page()
        log.info("Browser launched (headless=%s)", headless)
        return self

    def open_url(self, url: str):
        """Navigate to URL."""
        if not self.page:
            raise BrowserError("Browser not launched")
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        log.info("Opened: %s", url)

    def search(self, query: str, engine: str = "https://www.google.com/search?q="):
        """Search query and return results text."""
        if not self.page:
            raise BrowserError("Browser not launched")
        search_url = f"{engine}{query.replace(' ', '+')}"
        self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        # Extract result snippets
        results = self.page.evaluate("""
            () => {
                const items = document.querySelectorAll('div.g');
                return Array.from(items).slice(0, 10).map(el => {
                    const title = el.querySelector('h3')?.innerText || '';
                    const snippet = el.querySelector('div[data-content-feature]')?.innerText
                        || el.querySelector('span')?.innerText
                        || '';
                    return title + ' — ' + snippet;
                }).filter(t => t.length > 10);
            }
        """)
        log.info("Search '%s': %d results", query, len(results))
        return results

    def read_page(self, selector: Optional[str] = None) -> str:
        """Read page content, optionally scoped to selector."""
        if not self.page:
            raise BrowserError("Browser not launched")
        if selector:
            el = self.page.locator(selector).first
            return el.inner_text() if el.count() > 0 else ""
        return self.page.content()

    def click(self, selector: str):
        """Click element by selector."""
        if not self.page:
            raise BrowserError("Browser not launched")
        self.page.click(selector, timeout=10000)
        log.info("Clicked: %s", selector)

    def type_text(self, selector: str, text: str):
        """Type into input field."""
        if not self.page:
            raise BrowserError("Browser not launched")
        self.page.fill(selector, text)
        log.info("Typed into: %s", selector)

    def press(self, selector: str, key: str):
        """Press key on element or page."""
        if not self.page:
            raise BrowserError("Browser not launched")
        self.page.press(selector, key)
        log.info("Pressed: %s on %s", key, selector)

    def scroll(self, direction: str = "down", amount: int = 300):
        """Scroll page: 'up' or 'down', pixel amount."""
        if not self.page:
            raise BrowserError("Browser not launched")
        if direction == "down":
            self.page.evaluate(f"window.scrollBy(0, {amount})")
        else:
            self.page.evaluate(f"window.scrollBy(0, -{amount})")
        log.info("Scrolled %s by %dpx", direction, amount)

    def take_screenshot(self, path: Optional[str] = None) -> bytes:
        """Take screenshot, return bytes."""
        if not self.page:
            raise BrowserError("Browser not launched")
        return self.page.screenshot(path=path)

    def close(self):
        """Clean up browser."""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        log.info("Browser closed")


# Singleton-ish usage
def get_browser() -> BrowserTools:
    bt = BrowserTools()
    bt.launch(headless=True)
    return bt