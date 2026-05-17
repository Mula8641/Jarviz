"""Tests for tools.py — executor routing, argument handling, error safety."""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def _stub_deps():
    cfg = types.ModuleType("config")
    cfg.config = {}
    sys.modules.setdefault("config", cfg)

    err = types.ModuleType("errors")
    err.BrowserError = Exception
    err.retry = lambda *a, **k: (lambda f: f)
    sys.modules.setdefault("errors", err)

    # Stub browser_tools so lazy imports inside tools.py resolve
    bt_stub = types.ModuleType("browser_tools")
    bt_stub.get_browser = MagicMock()
    bt_stub.shutdown_browser = MagicMock()
    sys.modules.setdefault("browser_tools", bt_stub)


_stub_deps()

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("tools", Path(__file__).parent.parent / "tools.py")
tools_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tools_mod)


class TestToolDefinitions(unittest.TestCase):
    def test_all_tools_have_type_function(self):
        for t in tools_mod.TOOL_DEFINITIONS:
            self.assertEqual(t["type"], "function")

    def test_all_tools_have_name_and_description(self):
        for t in tools_mod.TOOL_DEFINITIONS:
            fn = t["function"]
            self.assertIn("name", fn)
            self.assertIn("description", fn)
            self.assertGreater(len(fn["description"]), 10)

    def test_expected_tools_present(self):
        names = {t["function"]["name"] for t in tools_mod.TOOL_DEFINITIONS}
        for expected in ["search_web", "open_url", "describe_screen",
                         "get_memory_facts", "remember_fact", "launch_app", "read_page_content"]:
            self.assertIn(expected, names)

    def test_required_parameters_are_lists(self):
        for t in tools_mod.TOOL_DEFINITIONS:
            params = t["function"].get("parameters", {})
            self.assertIsInstance(params.get("required", []), list)


class TestExecuteToolRouting(unittest.TestCase):
    def test_unknown_tool_returns_message(self):
        result = tools_mod.execute_tool("nonexistent_tool", {})
        self.assertIn("Unknown tool", result)

    def test_bad_arguments_returns_error_not_exception(self):
        # search_web requires 'query' — passing wrong arg should return error string
        with patch.object(tools_mod, "_search_web", side_effect=TypeError("missing query")):
            result = tools_mod.execute_tool("search_web", {})
        self.assertIn("invalid arguments", result.lower())

    def test_tool_exception_returns_string(self):
        with patch.object(tools_mod, "_search_web", side_effect=RuntimeError("network error")):
            result = tools_mod.execute_tool("search_web", {"query": "test"})
        self.assertIn("failed", result.lower())


class TestSearchWeb(unittest.TestCase):
    def test_returns_joined_results(self):
        bt_mock = MagicMock()
        bt_mock.search.return_value = ["Result 1 — snippet", "Result 2 — snippet"]
        with patch("browser_tools.get_browser", return_value=bt_mock):
            result = tools_mod._search_web("test query")
        self.assertIn("Result 1", result)

    def test_empty_results(self):
        bt_mock = MagicMock()
        bt_mock.search.return_value = []
        with patch("browser_tools.get_browser", return_value=bt_mock):
            result = tools_mod._search_web("empty query")
        self.assertEqual(result, "No results found.")


class TestOpenUrl(unittest.TestCase):
    def test_prepends_https_if_missing(self):
        bt_mock = MagicMock()
        bt_mock.read_page.return_value = "page content"
        captured = {}

        def fake_open(url):
            captured["url"] = url

        bt_mock.open_url.side_effect = fake_open
        with patch("browser_tools.get_browser", return_value=bt_mock):
            tools_mod._open_url("google.com")
        self.assertTrue(captured["url"].startswith("https://"))

    def test_keeps_existing_https(self):
        bt_mock = MagicMock()
        bt_mock.read_page.return_value = "content"
        captured = {}
        bt_mock.open_url.side_effect = lambda url: captured.update({"url": url})
        with patch("browser_tools.get_browser", return_value=bt_mock):
            tools_mod._open_url("https://example.com")
        self.assertEqual(captured["url"], "https://example.com")


class TestRememberFact(unittest.TestCase):
    def test_calls_set_fact_and_returns_confirmation(self):
        mem_mock = MagicMock()
        with patch.dict(sys.modules, {"memory": mem_mock}):
            result = tools_mod._remember_fact("color", "blue")
        self.assertIn("color", result)
        self.assertIn("blue", result)

    def test_result_is_string(self):
        mem_mock = MagicMock()
        with patch.dict(sys.modules, {"memory": mem_mock}):
            result = tools_mod._remember_fact("k", "v")
        self.assertIsInstance(result, str)


class TestGetMemoryFacts(unittest.TestCase):
    def test_returns_formatted_facts(self):
        mem_mock = MagicMock()
        mem_mock.get_facts.return_value = {"name": "Alice", "city": "Berlin"}
        with patch.dict(sys.modules, {"memory": mem_mock}):
            result = tools_mod._get_memory_facts()
        self.assertIn("name", result)
        self.assertIn("Alice", result)

    def test_empty_facts(self):
        mem_mock = MagicMock()
        mem_mock.get_facts.return_value = {}
        with patch.dict(sys.modules, {"memory": mem_mock}):
            result = tools_mod._get_memory_facts()
        self.assertIn("No facts", result)


class TestLaunchApp(unittest.TestCase):
    def test_successful_launch(self):
        with patch("tools.subprocess.Popen") as mock_popen:
            result = tools_mod._launch_app("notepad")
        self.assertIn("Launched", result)
        mock_popen.assert_called_once()

    def test_failed_launch_returns_string(self):
        with patch("tools.subprocess.Popen", side_effect=FileNotFoundError("not found")):
            result = tools_mod._launch_app("badapp")
        self.assertIn("Failed", result)
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
