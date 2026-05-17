"""Tests for read_clipboard / write_clipboard tools."""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import importlib.util
from pathlib import Path


def _setup():
    cfg = types.ModuleType("config")
    cfg.config = {}
    sys.modules["config"] = cfg

    bt_stub = types.ModuleType("browser_tools")
    bt_stub.get_browser = MagicMock()
    bt_stub.shutdown_browser = MagicMock()
    sys.modules.setdefault("browser_tools", bt_stub)


_setup()

spec = importlib.util.spec_from_file_location("tools_cb", Path(__file__).parent.parent / "tools.py")
tools_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools_mod)


class TestReadClipboard(unittest.TestCase):
    def _patch_pyperclip(self, paste_return):
        pc = MagicMock()
        pc.paste.return_value = paste_return
        return patch.dict(sys.modules, {"pyperclip": pc}), pc

    def test_returns_clipboard_content(self):
        pc = MagicMock()
        pc.paste.return_value = "Hello from clipboard"
        with patch.dict(sys.modules, {"pyperclip": pc}):
            result = tools_mod._read_clipboard()
        self.assertIn("Hello from clipboard", result)

    def test_empty_clipboard_message(self):
        pc = MagicMock()
        pc.paste.return_value = ""
        with patch.dict(sys.modules, {"pyperclip": pc}):
            result = tools_mod._read_clipboard()
        self.assertIn("empty", result.lower())

    def test_truncates_long_content(self):
        pc = MagicMock()
        pc.paste.return_value = "x" * 3000
        with patch.dict(sys.modules, {"pyperclip": pc}):
            result = tools_mod._read_clipboard()
        # Should be capped at 2000 chars of content
        self.assertLessEqual(len(result), 2100)

    def test_pyperclip_exception_returns_error_string(self):
        pc = MagicMock()
        pc.paste.side_effect = Exception("no display")
        with patch.dict(sys.modules, {"pyperclip": pc}):
            result = tools_mod._read_clipboard()
        self.assertIn("Could not read clipboard", result)
        self.assertIsInstance(result, str)

    def test_result_is_always_string(self):
        pc = MagicMock()
        pc.paste.return_value = "some text"
        with patch.dict(sys.modules, {"pyperclip": pc}):
            result = tools_mod._read_clipboard()
        self.assertIsInstance(result, str)


class TestWriteClipboard(unittest.TestCase):
    def test_copies_text_and_returns_preview(self):
        pc = MagicMock()
        with patch.dict(sys.modules, {"pyperclip": pc}):
            result = tools_mod._write_clipboard("Hello world")
        pc.copy.assert_called_once_with("Hello world")
        self.assertIn("Hello world", result)

    def test_long_text_preview_truncated(self):
        pc = MagicMock()
        with patch.dict(sys.modules, {"pyperclip": pc}):
            result = tools_mod._write_clipboard("a" * 200)
        self.assertIn("...", result)

    def test_short_text_no_ellipsis(self):
        pc = MagicMock()
        with patch.dict(sys.modules, {"pyperclip": pc}):
            result = tools_mod._write_clipboard("short text")
        self.assertNotIn("...", result)

    def test_pyperclip_exception_returns_error_string(self):
        pc = MagicMock()
        pc.copy.side_effect = Exception("clipboard unavailable")
        with patch.dict(sys.modules, {"pyperclip": pc}):
            result = tools_mod._write_clipboard("test")
        self.assertIn("Could not write to clipboard", result)

    def test_result_is_always_string(self):
        pc = MagicMock()
        with patch.dict(sys.modules, {"pyperclip": pc}):
            result = tools_mod._write_clipboard("text")
        self.assertIsInstance(result, str)


class TestClipboardViaExecute(unittest.TestCase):
    def test_execute_read_clipboard(self):
        with patch.object(tools_mod, "_read_clipboard", return_value="clipboard text") as mock_fn:
            result = tools_mod.execute_tool("read_clipboard", {})
        mock_fn.assert_called_once()
        self.assertEqual(result, "clipboard text")

    def test_execute_write_clipboard(self):
        with patch.object(tools_mod, "_write_clipboard", return_value="Copied") as mock_fn:
            result = tools_mod.execute_tool("write_clipboard", {"text": "hello"})
        mock_fn.assert_called_once_with(text="hello")

    def test_read_clipboard_in_tool_definitions(self):
        names = {t["function"]["name"] for t in tools_mod.TOOL_DEFINITIONS}
        self.assertIn("read_clipboard", names)
        self.assertIn("write_clipboard", names)


if __name__ == "__main__":
    unittest.main()
