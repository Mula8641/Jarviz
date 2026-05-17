"""Tests for llm.py multi-backend routing — OpenAI, Anthropic, priority chain."""
import sys
import types
import json
import unittest
from unittest.mock import MagicMock, patch


def _stub_config(keys: dict):
    cfg_mod = types.ModuleType("config")
    cfg_mod.config = {
        "minimax_api_key": "", "openai_api_key": "", "openai_model": "gpt-4o",
        "anthropic_api_key": "", "anthropic_model": "claude-sonnet-4-6",
        "ollama_base_url": "", "ollama_model": "llama3.2",
        **keys,
    }
    sys.modules["config"] = cfg_mod
    return cfg_mod.config


import importlib.util
from pathlib import Path


def _load_llm(cfg: dict):
    cfg_mod = types.ModuleType("config")
    cfg_mod.config = cfg
    sys.modules["config"] = cfg_mod
    spec = importlib.util.spec_from_file_location(
        f"llm_be_{id(cfg)}", Path(__file__).parent.parent / "llm.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.config = cfg
    return mod


def _fake_client(body: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    resp.raise_for_status = MagicMock(
        side_effect=None if status < 400 else Exception(f"HTTP {status}")
    )
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.return_value = resp
    return client


OPENAI_CHAT_RESP = {"choices": [{"message": {"role": "assistant", "content": "Hello from OpenAI"}}]}
ANTHROPIC_CHAT_RESP = {"content": [{"type": "text", "text": "Hello from Anthropic"}]}
OPENAI_TOOL_RESP = {
    "choices": [{
        "message": {
            "role": "assistant", "content": "",
            "tool_calls": [{"id": "c1", "type": "function",
                            "function": {"name": "search_web", "arguments": '{"query":"x"}'}}],
        }
    }]
}
ANTHROPIC_TOOL_RESP = {
    "content": [
        {"type": "tool_use", "id": "tu1", "name": "search_web", "input": {"query": "x"}},
    ]
}

DUMMY_TOOLS = [{"type": "function", "function": {"name": "search_web",
                "description": "search", "parameters": {"type": "object", "properties": {}}}}]


class TestOpenAIChat(unittest.TestCase):
    def setUp(self):
        self.cfg = _stub_config({"openai_api_key": "sk-test"})
        self.llm = _load_llm(self.cfg)

    def test_returns_openai_response(self):
        with patch.object(self.llm.httpx, "Client", return_value=_fake_client(OPENAI_CHAT_RESP)):
            result = self.llm.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello from OpenAI")

    def test_uses_openai_url(self):
        captured = {}
        client = _fake_client(OPENAI_CHAT_RESP)
        client.post.side_effect = lambda url, **k: (captured.update({"url": url}),
                                                     _fake_client(OPENAI_CHAT_RESP).post(url))[1]
        real_resp = MagicMock()
        real_resp.raise_for_status.return_value = None
        real_resp.json.return_value = OPENAI_CHAT_RESP
        client.post.side_effect = lambda url, **k: (captured.update({"url": url}), real_resp)[1]
        with patch.object(self.llm.httpx, "Client", return_value=client):
            self.llm.chat([{"role": "user", "content": "hi"}])
        self.assertIn("openai.com", captured.get("url", ""))

    def test_sends_configured_model(self):
        self.cfg["openai_model"] = "gpt-4o-mini"
        captured = {}
        client = _fake_client(OPENAI_CHAT_RESP)
        real_resp = MagicMock()
        real_resp.raise_for_status.return_value = None
        real_resp.json.return_value = OPENAI_CHAT_RESP
        client.post.side_effect = lambda url, json=None, **k: (
            captured.update({"model": (json or {}).get("model")}), real_resp
        )[1]
        with patch.object(self.llm.httpx, "Client", return_value=client):
            self.llm.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(captured.get("model"), "gpt-4o-mini")


class TestAnthropicChat(unittest.TestCase):
    def setUp(self):
        self.cfg = _stub_config({"anthropic_api_key": "sk-ant-test"})
        self.llm = _load_llm(self.cfg)

    def test_returns_anthropic_response(self):
        with patch.object(self.llm.httpx, "Client", return_value=_fake_client(ANTHROPIC_CHAT_RESP)):
            result = self.llm.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello from Anthropic")

    def test_system_message_extracted(self):
        captured = {}
        client = _fake_client(ANTHROPIC_CHAT_RESP)
        real_resp = MagicMock()
        real_resp.raise_for_status.return_value = None
        real_resp.json.return_value = ANTHROPIC_CHAT_RESP
        client.post.side_effect = lambda url, json=None, **k: (
            captured.update({"payload": json}), real_resp
        )[1]
        msgs = [{"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "hi"}]
        with patch.object(self.llm.httpx, "Client", return_value=client):
            self.llm.chat(msgs)
        self.assertEqual(captured["payload"]["system"], "You are helpful")
        user_msgs = captured["payload"]["messages"]
        self.assertTrue(all(m["role"] != "system" for m in user_msgs))


class TestOpenAIToolCalling(unittest.TestCase):
    def setUp(self):
        self.cfg = _stub_config({"openai_api_key": "sk-test"})
        self.llm = _load_llm(self.cfg)

    def test_returns_tool_calls(self):
        with patch.object(self.llm.httpx, "Client", return_value=_fake_client(OPENAI_TOOL_RESP)):
            result = self.llm.chat_with_tools([{"role": "user", "content": "x"}], DUMMY_TOOLS)
        self.assertTrue(result.get("tool_calls"))
        self.assertEqual(result["tool_calls"][0]["function"]["name"], "search_web")

    def test_returns_content_when_no_tool_calls(self):
        resp = {"choices": [{"message": {"role": "assistant", "content": "plain answer",
                                          "tool_calls": None}}]}
        with patch.object(self.llm.httpx, "Client", return_value=_fake_client(resp)):
            result = self.llm.chat_with_tools([{"role": "user", "content": "x"}], DUMMY_TOOLS)
        self.assertEqual(result["content"], "plain answer")
        self.assertFalse(result.get("tool_calls"))


class TestAnthropicToolCalling(unittest.TestCase):
    def setUp(self):
        self.cfg = _stub_config({"anthropic_api_key": "sk-ant-test"})
        self.llm = _load_llm(self.cfg)

    def test_tool_calls_translated_to_openai_format(self):
        with patch.object(self.llm.httpx, "Client", return_value=_fake_client(ANTHROPIC_TOOL_RESP)):
            result = self.llm.chat_with_tools([{"role": "user", "content": "x"}], DUMMY_TOOLS)
        self.assertTrue(result.get("tool_calls"))
        tc = result["tool_calls"][0]
        self.assertEqual(tc["type"], "function")
        self.assertEqual(tc["function"]["name"], "search_web")
        args = json.loads(tc["function"]["arguments"])
        self.assertEqual(args["query"], "x")

    def test_tool_schema_translated_to_anthropic_format(self):
        captured = {}
        client = _fake_client(ANTHROPIC_TOOL_RESP)
        real_resp = MagicMock()
        real_resp.raise_for_status.return_value = None
        real_resp.json.return_value = ANTHROPIC_TOOL_RESP
        client.post.side_effect = lambda url, json=None, **k: (
            captured.update({"payload": json}), real_resp
        )[1]
        with patch.object(self.llm.httpx, "Client", return_value=client):
            self.llm.chat_with_tools([{"role": "user", "content": "x"}], DUMMY_TOOLS)
        ant_tool = captured["payload"]["tools"][0]
        self.assertIn("name", ant_tool)
        self.assertIn("input_schema", ant_tool)
        self.assertNotIn("type", ant_tool)  # OpenAI "type":"function" removed


class TestPriorityChain(unittest.TestCase):
    def test_minimax_used_when_key_set(self):
        cfg = _stub_config({
            "minimax_api_key": "mm-key",
            "openai_api_key": "oa-key",
            "anthropic_api_key": "ant-key",
        })
        llm = _load_llm(cfg)
        captured = {}
        client = _fake_client(OPENAI_CHAT_RESP)
        real_resp = MagicMock()
        real_resp.raise_for_status.return_value = None
        real_resp.json.return_value = OPENAI_CHAT_RESP
        client.post.side_effect = lambda url, **k: (captured.update({"url": url}), real_resp)[1]
        with patch.object(llm.httpx, "Client", return_value=client):
            llm.chat([{"role": "user", "content": "hi"}])
        self.assertIn("minimax", captured.get("url", ""))

    def test_openai_used_when_minimax_missing(self):
        cfg = _stub_config({"openai_api_key": "oa-key"})
        llm = _load_llm(cfg)
        captured = {}
        client = _fake_client(OPENAI_CHAT_RESP)
        real_resp = MagicMock()
        real_resp.raise_for_status.return_value = None
        real_resp.json.return_value = OPENAI_CHAT_RESP
        client.post.side_effect = lambda url, **k: (captured.update({"url": url}), real_resp)[1]
        with patch.object(llm.httpx, "Client", return_value=client):
            llm.chat([{"role": "user", "content": "hi"}])
        self.assertIn("openai", captured.get("url", ""))

    def test_anthropic_used_when_others_missing(self):
        cfg = _stub_config({"anthropic_api_key": "ant-key"})
        llm = _load_llm(cfg)
        captured = {}
        client = _fake_client(ANTHROPIC_CHAT_RESP)
        real_resp = MagicMock()
        real_resp.raise_for_status.return_value = None
        real_resp.json.return_value = ANTHROPIC_CHAT_RESP
        client.post.side_effect = lambda url, **k: (captured.update({"url": url}), real_resp)[1]
        with patch.object(llm.httpx, "Client", return_value=client):
            llm.chat([{"role": "user", "content": "hi"}])
        self.assertIn("anthropic", captured.get("url", ""))

    def test_no_keys_returns_error_string(self):
        cfg = _stub_config({})
        llm = _load_llm(cfg)
        result = llm.chat([{"role": "user", "content": "hi"}])
        self.assertIn("no llm backend", result.lower())

    def test_falls_through_to_next_on_failure(self):
        cfg = _stub_config({"minimax_api_key": "mm-key", "openai_api_key": "oa-key"})
        llm = _load_llm(cfg)
        call_count = {"n": 0}
        real_resp = MagicMock()
        real_resp.raise_for_status.return_value = None
        real_resp.json.return_value = OPENAI_CHAT_RESP

        def side_effect(url, **k):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("MiniMax down")
            return real_resp

        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.post.side_effect = side_effect

        with patch.object(llm.httpx, "Client", return_value=client):
            result = llm.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello from OpenAI")
        self.assertEqual(call_count["n"], 2)


if __name__ == "__main__":
    unittest.main()
