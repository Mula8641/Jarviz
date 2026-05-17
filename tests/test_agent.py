"""Tests for agent.py — agentic loop: no-tool path, single tool, chained tools, max iterations."""
import sys
import types
import json
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

    # Stub llm so agent's top-level import resolves
    llm_stub = types.ModuleType("llm")
    llm_stub.chat_with_tools = MagicMock()
    llm_stub.chat = MagicMock(return_value="fallback")
    sys.modules["llm"] = llm_stub


_stub_deps()

import importlib.util
from pathlib import Path

# Load tools module
_t_spec = importlib.util.spec_from_file_location("tools", Path(__file__).parent.parent / "tools.py")
tools_mod = importlib.util.module_from_spec(_t_spec)
sys.modules["tools"] = tools_mod
_t_spec.loader.exec_module(tools_mod)

# Load agent module
_a_spec = importlib.util.spec_from_file_location("agent", Path(__file__).parent.parent / "agent.py")
agent_mod = importlib.util.module_from_spec(_a_spec)
sys.modules["agent"] = agent_mod
_a_spec.loader.exec_module(agent_mod)


def _make_text_response(text: str) -> dict:
    return {"content": text, "tool_calls": None}


def _make_tool_response(name: str, args: dict, call_id: str = "call_1") -> dict:
    return {
        "content": "",
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(args),
            },
        }],
    }


class TestAgentNoTools(unittest.TestCase):
    def test_returns_llm_answer_directly(self):
        with patch.object(agent_mod, "chat_with_tools", return_value=_make_text_response("Hello!")):
            result = agent_mod.run([{"role": "user", "content": "Hi"}])
        self.assertEqual(result, "Hello!")

    def test_empty_content_returns_fallback(self):
        with patch.object(agent_mod, "chat_with_tools", return_value={"content": "", "tool_calls": None}):
            result = agent_mod.run([{"role": "user", "content": "?"}])
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_status_callback_not_called_on_direct_answer(self):
        cb = MagicMock()
        with patch.object(agent_mod, "chat_with_tools", return_value=_make_text_response("Done")):
            agent_mod.run([{"role": "user", "content": "x"}], status_callback=cb)
        cb.assert_not_called()


class TestAgentSingleTool(unittest.TestCase):
    def test_tool_called_then_final_answer(self):
        responses = [
            _make_tool_response("search_web", {"query": "AI news"}),
            _make_text_response("Here are the latest AI news..."),
        ]
        it = iter(responses)

        with patch.object(agent_mod, "chat_with_tools", side_effect=lambda *a: next(it)):
            with patch.object(agent_mod, "execute_tool", return_value="Result 1\nResult 2") as mock_exec:
                result = agent_mod.run([{"role": "user", "content": "Search AI news"}])

        mock_exec.assert_called_once_with("search_web", {"query": "AI news"})
        self.assertEqual(result, "Here are the latest AI news...")

    def test_tool_result_appended_to_messages(self):
        captured_messages = []

        def fake_chat(messages, tools):
            captured_messages.append(list(messages))
            if len(captured_messages) == 1:
                return _make_tool_response("remember_fact", {"key": "color", "value": "blue"})
            return _make_text_response("Got it!")

        with patch.object(agent_mod, "chat_with_tools", side_effect=fake_chat):
            with patch.object(agent_mod, "execute_tool", return_value="Remembered: color = blue"):
                agent_mod.run([{"role": "user", "content": "Remember color is blue"}])

        second_call_msgs = captured_messages[1]
        roles = [m["role"] for m in second_call_msgs]
        self.assertIn("tool", roles)

    def test_status_callback_called_with_tool_name(self):
        cb = MagicMock()
        responses = [
            _make_tool_response("search_web", {"query": "test"}),
            _make_text_response("Done"),
        ]
        it = iter(responses)

        with patch.object(agent_mod, "chat_with_tools", side_effect=lambda *a: next(it)):
            with patch.object(agent_mod, "execute_tool", return_value="results"):
                agent_mod.run([{"role": "user", "content": "test"}], status_callback=cb)

        cb.assert_called_once()
        self.assertIn("Search Web", cb.call_args[0][0])


class TestAgentChainedTools(unittest.TestCase):
    def test_two_tools_then_answer(self):
        responses = [
            _make_tool_response("search_web", {"query": "weather Berlin"}, "c1"),
            _make_tool_response("open_url", {"url": "https://weather.com"}, "c2"),
            _make_text_response("Berlin is 18°C and sunny."),
        ]
        it = iter(responses)
        tool_calls = []

        def fake_exec(name, args):
            tool_calls.append(name)
            return f"Result from {name}"

        with patch.object(agent_mod, "chat_with_tools", side_effect=lambda *a: next(it)):
            with patch.object(agent_mod, "execute_tool", side_effect=fake_exec):
                result = agent_mod.run([{"role": "user", "content": "Berlin weather"}])

        self.assertEqual(tool_calls, ["search_web", "open_url"])
        self.assertIn("18°C", result)


class TestAgentMaxIterations(unittest.TestCase):
    def test_max_iterations_triggers_final_chat(self):
        def always_tool(messages, tools):
            return _make_tool_response("search_web", {"query": "loop"})

        plain_chat_result = "Here's what I found after extensive research."

        with patch.object(agent_mod, "chat_with_tools", side_effect=always_tool):
            with patch.object(agent_mod, "execute_tool", return_value="result"):
                with patch.object(agent_mod, "chat", return_value=plain_chat_result) as mock_plain:
                    result = agent_mod.run([{"role": "user", "content": "anything"}])

        mock_plain.assert_called_once()
        self.assertEqual(result, plain_chat_result)

    def test_iteration_count_respected(self):
        call_count = {"n": 0}

        def count_calls(messages, tools):
            call_count["n"] += 1
            return _make_tool_response("search_web", {"query": "x"})

        with patch.object(agent_mod, "chat_with_tools", side_effect=count_calls):
            with patch.object(agent_mod, "execute_tool", return_value="r"):
                with patch.object(agent_mod, "chat", return_value="done"):
                    agent_mod.run([{"role": "user", "content": "x"}])

        self.assertEqual(call_count["n"], agent_mod.MAX_ITERATIONS)


class TestAgentArgumentParsing(unittest.TestCase):
    def test_handles_invalid_json_arguments(self):
        bad_response = {
            "content": "",
            "tool_calls": [{
                "id": "c1",
                "type": "function",
                "function": {"name": "search_web", "arguments": "NOT JSON"},
            }],
        }
        responses = [bad_response, _make_text_response("ok")]
        it = iter(responses)

        with patch.object(agent_mod, "chat_with_tools", side_effect=lambda *a: next(it)):
            with patch.object(agent_mod, "execute_tool", return_value="result") as mock_exec:
                agent_mod.run([{"role": "user", "content": "test"}])

        mock_exec.assert_called_once_with("search_web", {})


if __name__ == "__main__":
    unittest.main()
