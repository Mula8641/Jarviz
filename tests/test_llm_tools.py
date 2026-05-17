"""Tests for llm.py — chat_with_tools() response parsing, fallback chain."""
import sys
import types
import json
import unittest
from unittest.mock import MagicMock, patch, call


def _stub_deps():
    cfg = types.ModuleType("config")
    cfg.config = {
        "minimax_api_key": "test_key",
        "ollama_base_url": "",
        "ollama_model": "llama3.2",
    }
    sys.modules["config"] = cfg


_stub_deps()

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("llm_real", Path(__file__).parent.parent / "llm.py")
llm_mod = importlib.util.module_from_spec(_spec)
sys.modules["llm_real"] = llm_mod
_spec.loader.exec_module(llm_mod)

# Give tests access to the config dict so we can mutate it
_cfg = sys.modules["config"].config

DUMMY_TOOLS = [{"type": "function", "function": {"name": "search_web", "parameters": {}}}]


def _mock_http_client(response_body: dict, status: int = 200):
    """Build a mock httpx Client context manager that returns a fake response."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = response_body
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    else:
        resp.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = resp
    return mock_client


class TestChatWithToolsTextResponse(unittest.TestCase):
    def setUp(self):
        _cfg["minimax_api_key"] = "test_key"
        _cfg["ollama_base_url"] = ""
        llm_mod.config = _cfg

    def _api_resp(self, content: str) -> dict:
        return {
            "choices": [{
                "message": {"role": "assistant", "content": content, "tool_calls": None}
            }]
        }

    def test_returns_content_when_no_tool_calls(self):
        mock_client = _mock_http_client(self._api_resp("Hello!"))
        with patch.object(llm_mod.httpx, "Client", return_value=mock_client):
            result = llm_mod.chat_with_tools([{"role": "user", "content": "hi"}], DUMMY_TOOLS)
        self.assertEqual(result["content"], "Hello!")
        self.assertFalse(result.get("tool_calls"))

    def test_returns_tool_calls_when_present(self):
        tool_calls = [{
            "id": "call_1",
            "type": "function",
            "function": {"name": "search_web", "arguments": '{"query": "news"}'},
        }]
        body = {
            "choices": [{
                "message": {"role": "assistant", "content": "", "tool_calls": tool_calls}
            }]
        }
        mock_client = _mock_http_client(body)
        with patch.object(llm_mod.httpx, "Client", return_value=mock_client):
            result = llm_mod.chat_with_tools([{"role": "user", "content": "search"}], DUMMY_TOOLS)
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["tool_calls"][0]["function"]["name"], "search_web")

    def test_falls_back_to_plain_chat_when_minimax_fails(self):
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = Exception("timeout")

        with patch.object(llm_mod.httpx, "Client", return_value=mock_client):
            with patch.object(llm_mod, "chat", return_value="fallback answer") as mock_chat:
                result = llm_mod.chat_with_tools(
                    [{"role": "user", "content": "hi"}], DUMMY_TOOLS
                )
        self.assertEqual(result["content"], "fallback answer")
        mock_chat.assert_called_once()


class TestChatWithToolsOllamaFallback(unittest.TestCase):
    def setUp(self):
        _cfg["minimax_api_key"] = ""
        _cfg["ollama_base_url"] = "http://localhost:11434"
        _cfg["ollama_model"] = "llama3.2"
        llm_mod.config = _cfg

    def tearDown(self):
        _cfg["minimax_api_key"] = "test_key"
        _cfg["ollama_base_url"] = ""

    def test_ollama_text_response(self):
        body = {"message": {"role": "assistant", "content": "ollama says hi", "tool_calls": None}}
        mock_client = _mock_http_client(body)
        with patch.object(llm_mod.httpx, "Client", return_value=mock_client):
            result = llm_mod.chat_with_tools([{"role": "user", "content": "hi"}], DUMMY_TOOLS)
        self.assertEqual(result["content"], "ollama says hi")

    def test_ollama_tool_call_response(self):
        tool_calls = [{
            "id": "oc_1",
            "type": "function",
            "function": {"name": "search_web", "arguments": {"query": "x"}},
        }]
        body = {"message": {"role": "assistant", "content": "", "tool_calls": tool_calls}}
        mock_client = _mock_http_client(body)
        with patch.object(llm_mod.httpx, "Client", return_value=mock_client):
            result = llm_mod.chat_with_tools([{"role": "user", "content": "x"}], DUMMY_TOOLS)
        self.assertTrue(result.get("tool_calls"))


class TestChatWithToolsPayloadShape(unittest.TestCase):
    def setUp(self):
        _cfg["minimax_api_key"] = "test_key"
        _cfg["ollama_base_url"] = ""
        llm_mod.config = _cfg

    def test_payload_contains_tools_and_tool_choice(self):
        captured = {}

        def fake_post(url, json=None, headers=None, **kwargs):
            captured["payload"] = json
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.json.return_value = {
                "choices": [{"message": {"content": "ok", "tool_calls": None}}]
            }
            return resp

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = fake_post

        with patch.object(llm_mod.httpx, "Client", return_value=mock_client):
            llm_mod.chat_with_tools([{"role": "user", "content": "x"}], DUMMY_TOOLS)

        self.assertIn("tools", captured["payload"])
        self.assertEqual(captured["payload"]["tool_choice"], "auto")
        self.assertEqual(captured["payload"]["tools"], DUMMY_TOOLS)


if __name__ == "__main__":
    unittest.main()
