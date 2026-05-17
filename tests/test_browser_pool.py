"""Tests for browser_tools.py — pool singleton, is_alive, shutdown."""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, PropertyMock


def _stub_deps():
    cfg = types.ModuleType("config")
    cfg.config = {}
    sys.modules.setdefault("config", cfg)

    err = types.ModuleType("errors")
    err.BrowserError = Exception
    err.retry = lambda *a, **k: (lambda f: f)
    sys.modules.setdefault("errors", err)

    # Stub playwright so the import doesn't fail
    pw_mock = MagicMock()
    sys.modules.setdefault("playwright", pw_mock)
    sys.modules.setdefault("playwright.sync_api", pw_mock)


_stub_deps()

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "browser_tools_test",
    Path(__file__).parent.parent / "browser_tools.py",
)
bt_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bt_mod)


class TestBrowserToolsIsAlive(unittest.TestCase):
    def test_is_alive_false_when_no_browser(self):
        bt = bt_mod.BrowserTools()
        self.assertFalse(bt.is_alive())

    def test_is_alive_true_when_browser_connected(self):
        bt = bt_mod.BrowserTools()
        bt.browser = MagicMock()
        bt.browser.is_connected.return_value = True
        self.assertTrue(bt.is_alive())

    def test_is_alive_false_when_browser_disconnected(self):
        bt = bt_mod.BrowserTools()
        bt.browser = MagicMock()
        bt.browser.is_connected.return_value = False
        self.assertFalse(bt.is_alive())

    def test_is_alive_false_when_is_connected_raises(self):
        bt = bt_mod.BrowserTools()
        bt.browser = MagicMock()
        bt.browser.is_connected.side_effect = Exception("crashed")
        self.assertFalse(bt.is_alive())


class TestBrowserPool(unittest.TestCase):
    def _fresh_pool(self):
        pool = bt_mod._BrowserPool()
        return pool

    def test_get_creates_new_instance_when_none(self):
        pool = self._fresh_pool()
        fake_bt = MagicMock()
        fake_bt.is_alive.return_value = True

        with patch.object(bt_mod, "BrowserTools", return_value=fake_bt):
            result = pool.get()

        self.assertIs(result, fake_bt)
        fake_bt.launch.assert_called_once_with(headless=True)

    def test_get_reuses_alive_instance(self):
        pool = self._fresh_pool()
        fake_bt = MagicMock()
        fake_bt.is_alive.return_value = True

        with patch.object(bt_mod, "BrowserTools", return_value=fake_bt):
            first = pool.get()
            second = pool.get()

        self.assertIs(first, second)
        # BrowserTools() should only be constructed once
        self.assertEqual(fake_bt.launch.call_count, 1)

    def test_get_recreates_dead_instance(self):
        pool = self._fresh_pool()

        dead_bt = MagicMock()
        dead_bt.is_alive.return_value = False

        new_bt = MagicMock()
        new_bt.is_alive.return_value = True

        # dead_bt is pre-created; BrowserTools() inside get() will return new_bt
        with patch.object(bt_mod, "BrowserTools", side_effect=[new_bt]):
            pool._bt = dead_bt  # inject the dead instance
            result = pool.get()

        self.assertIs(result, new_bt)
        dead_bt.close.assert_called_once()

    def test_shutdown_closes_browser(self):
        pool = self._fresh_pool()
        fake_bt = MagicMock()
        pool._bt = fake_bt
        pool.shutdown()
        fake_bt.close.assert_called_once()
        self.assertIsNone(pool._bt)

    def test_shutdown_safe_when_no_instance(self):
        pool = self._fresh_pool()
        pool.shutdown()  # should not raise


class TestBrowserToolsUrlHandling(unittest.TestCase):
    def test_open_url_calls_goto(self):
        bt = bt_mod.BrowserTools()
        bt.page = MagicMock()
        bt.open_url("https://example.com")
        bt.page.goto.assert_called_once_with(
            "https://example.com", wait_until="domcontentloaded", timeout=30000
        )

    def test_open_url_raises_when_no_page(self):
        bt = bt_mod.BrowserTools()
        bt.page = None
        with self.assertRaises(Exception):
            bt.open_url("https://example.com")

    def test_scroll_down(self):
        bt = bt_mod.BrowserTools()
        bt.page = MagicMock()
        bt.scroll("down", 500)
        bt.page.evaluate.assert_called_once_with("window.scrollBy(0, 500)")

    def test_scroll_up(self):
        bt = bt_mod.BrowserTools()
        bt.page = MagicMock()
        bt.scroll("up", 200)
        bt.page.evaluate.assert_called_once_with("window.scrollBy(0, -200)")


if __name__ == "__main__":
    unittest.main()
