"""Tests for attempt-then-escalate routing in llm.py."""
import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers to load llm with a fake config
# ---------------------------------------------------------------------------

def _make_cfg(**kwargs):
    """Return a minimal config dict for routing tests."""
    base = {
        "minimax_api_key": "mm-key",
        "openai_api_key": "",
        "anthropic_api_key": "ant-key",
        "openai_model": "gpt-4o",
        "anthropic_model": "claude-sonnet-4-6",
        "ollama_base_url": "",
        "ollama_model": "llama3.2",
        "routing_enabled": True,
        "escalation_backend": "anthropic",
    }
    base.update(kwargs)
    return base


def _load_llm(cfg: dict):
    """Load a fresh llm module with the given config dict injected."""
    cfg_mod = types.ModuleType("config")
    cfg_mod.config = cfg
    with patch.dict(sys.modules, {"config": cfg_mod}):
        if "llm" in sys.modules:
            del sys.modules["llm"]
        spec = importlib.util.spec_from_file_location(
            "llm", "/home/user/Jarviz/llm.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["llm"] = mod
        spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# _response_is_weak
# ---------------------------------------------------------------------------

class TestResponseIsWeak(unittest.TestCase):

    def setUp(self):
        self.llm = _load_llm(_make_cfg())

    def test_empty_string_is_weak(self):
        self.assertTrue(self.llm._response_is_weak(""))

    def test_none_is_weak(self):
        self.assertTrue(self.llm._response_is_weak(None))

    def test_very_short_is_weak(self):
        self.assertTrue(self.llm._response_is_weak("OK"))

    def test_uncertainty_phrase_is_weak(self):
        self.assertTrue(self.llm._response_is_weak("I'm not sure about that topic."))

    def test_cannot_phrase_is_weak(self):
        self.assertTrue(self.llm._response_is_weak("I cannot provide information on this."))

    def test_dont_know_is_weak(self):
        self.assertTrue(self.llm._response_is_weak("I don't know the answer to your question."))

    def test_normal_answer_not_weak(self):
        self.assertFalse(self.llm._response_is_weak(
            "The capital of France is Paris, located in the north of the country."
        ))

    def test_confident_short_answer_not_weak(self):
        self.assertFalse(self.llm._response_is_weak("The answer is 42. This is certain."))

    def test_beyond_my_is_weak(self):
        self.assertTrue(self.llm._response_is_weak("This is beyond my capabilities."))

    def test_outside_my_is_weak(self):
        self.assertTrue(self.llm._response_is_weak("That request is outside my expertise."))


# ---------------------------------------------------------------------------
# _should_skip_minimax
# ---------------------------------------------------------------------------

class TestShouldSkipMinimax(unittest.TestCase):

    def setUp(self):
        self.llm = _load_llm(_make_cfg())

    def _msgs(self, text):
        return [{"role": "user", "content": text}]

    def test_short_simple_not_skipped(self):
        self.assertFalse(self.llm._should_skip_minimax(self._msgs("What is the weather today?")))

    def test_over_60_words_skipped(self):
        long_msg = " ".join(["word"] * 65)
        self.assertTrue(self.llm._should_skip_minimax(self._msgs(long_msg)))

    def test_write_verb_skips(self):
        self.assertTrue(self.llm._should_skip_minimax(self._msgs("write a poem about the sea")))

    def test_code_verb_skips(self):
        self.assertTrue(self.llm._should_skip_minimax(self._msgs("code a Python script to parse CSV")))

    def test_implement_verb_skips(self):
        self.assertTrue(self.llm._should_skip_minimax(self._msgs("implement a binary search algorithm")))

    def test_generate_verb_skips(self):
        self.assertTrue(self.llm._should_skip_minimax(self._msgs("generate a cover letter for me")))

    def test_explain_verb_not_skipped(self):
        # "explain" is intentionally NOT in _SKIP_FIRST_WORDS
        self.assertFalse(self.llm._should_skip_minimax(self._msgs("explain 2+2")))

    def test_empty_messages_not_skipped(self):
        self.assertFalse(self.llm._should_skip_minimax([]))

    def test_system_msg_ignored(self):
        msgs = [
            {"role": "system", "content": "write me something long" * 10},
            {"role": "user", "content": "hi there"},
        ]
        self.assertFalse(self.llm._should_skip_minimax(msgs))


# ---------------------------------------------------------------------------
# chat() routing
# ---------------------------------------------------------------------------

class TestChatRouting(unittest.TestCase):

    def _msgs(self, text="hello"):
        return [{"role": "user", "content": text}]

    def test_minimax_strong_no_escalation(self):
        """MiniMax returns a confident answer → no escalation."""
        llm = _load_llm(_make_cfg())
        with patch.object(llm, "_openai_chat", return_value="Paris is the capital of France.") as mm_mock, \
             patch.object(llm, "_capable_chat") as cap_mock:
            result = llm.chat(self._msgs("What is the capital of France?"))
        self.assertEqual(result, "Paris is the capital of France.")
        cap_mock.assert_not_called()
        self.assertEqual(llm.last_used, "MiniMax")

    def test_minimax_weak_escalates(self):
        """MiniMax returns a weak answer → escalation to capable backend."""
        llm = _load_llm(_make_cfg())
        with patch.object(llm, "_openai_chat", return_value="I'm not sure about that."), \
             patch.object(llm, "_capable_chat", return_value="The correct answer is X.") as cap_mock, \
             patch.object(llm, "_capable_name", return_value="Claude (claude-sonnet-4-6)"):
            result = llm.chat(self._msgs("What is quantum entanglement?"))
        self.assertEqual(result, "The correct answer is X.")
        cap_mock.assert_called_once()

    def test_minimax_fails_escalates(self):
        """MiniMax raises exception → escalation to capable backend."""
        llm = _load_llm(_make_cfg())
        with patch.object(llm, "_openai_chat", side_effect=RuntimeError("timeout")), \
             patch.object(llm, "_capable_chat", return_value="Fallback answer.") as cap_mock, \
             patch.object(llm, "_capable_name", return_value="Claude (claude-sonnet-4-6)"):
            result = llm.chat(self._msgs())
        cap_mock.assert_called_once()
        self.assertEqual(result, "Fallback answer.")

    def test_long_message_skips_minimax(self):
        """>60 word message skips straight to capable backend."""
        llm = _load_llm(_make_cfg())
        long = " ".join(["word"] * 65)
        with patch.object(llm, "_openai_chat") as mm_mock, \
             patch.object(llm, "_capable_chat", return_value="Done.") as cap_mock, \
             patch.object(llm, "_capable_name", return_value="Claude"):
            llm.chat(self._msgs(long))
        # _openai_chat should NOT be called for MiniMax (base_url would be MINIMAX_URL)
        # We test that capable_chat was called
        cap_mock.assert_called_once()

    def test_generation_verb_skips_minimax(self):
        """'write ...' skips MiniMax."""
        llm = _load_llm(_make_cfg())
        with patch.object(llm, "_openai_chat") as mm_mock, \
             patch.object(llm, "_capable_chat", return_value="Here's your poem."), \
             patch.object(llm, "_capable_name", return_value="Claude"):
            llm.chat(self._msgs("write a haiku"))
        mm_mock.assert_not_called()

    def test_routing_disabled_uses_priority_chain(self):
        """routing_enabled=False → _priority_chain() is called, not routing logic."""
        llm = _load_llm(_make_cfg(routing_enabled=False))
        with patch.object(llm, "_priority_chain", return_value="chain result") as chain_mock, \
             patch.object(llm, "_openai_chat") as mm_mock:
            result = llm.chat(self._msgs())
        chain_mock.assert_called_once()
        self.assertEqual(result, "chain result")

    def test_no_minimax_key_skips_to_capable(self):
        """No minimax key → skip straight to capable."""
        llm = _load_llm(_make_cfg(minimax_api_key=""))
        with patch.object(llm, "_openai_chat") as mm_mock, \
             patch.object(llm, "_capable_chat", return_value="Capable answer."), \
             patch.object(llm, "_capable_name", return_value="Claude"):
            result = llm.chat(self._msgs())
        mm_mock.assert_not_called()
        self.assertEqual(result, "Capable answer.")


# ---------------------------------------------------------------------------
# chat_with_tools() routing
# ---------------------------------------------------------------------------

class TestToolRouting(unittest.TestCase):

    def _msgs(self, text="search for cats"):
        return [{"role": "user", "content": text}]

    def _tools(self):
        return [{"type": "function", "function": {"name": "search_web",
                 "description": "Search the web", "parameters": {}}}]

    def test_minimax_returns_tool_calls_not_escalated(self):
        """MiniMax chose a tool → it's working, don't escalate."""
        llm = _load_llm(_make_cfg())
        mm_result = {"tool_calls": [{"id": "1", "function": {"name": "search_web", "arguments": "{}"}}],
                     "content": ""}
        with patch.object(llm, "_openai_tools", return_value=mm_result), \
             patch.object(llm, "_capable_tools") as cap_mock:
            result = llm.chat_with_tools(self._msgs(), self._tools())
        self.assertEqual(result, mm_result)
        cap_mock.assert_not_called()
        self.assertEqual(llm.last_used, "MiniMax")

    def test_minimax_weak_answer_escalated(self):
        """MiniMax returns no tool calls and weak content → escalate."""
        llm = _load_llm(_make_cfg())
        mm_result = {"content": "I'm not sure what tool to use."}
        cap_result = {"tool_calls": [{"id": "2", "function": {"name": "search_web", "arguments": "{}"}}],
                      "content": ""}
        with patch.object(llm, "_openai_tools", return_value=mm_result), \
             patch.object(llm, "_capable_tools", return_value=cap_result) as cap_mock, \
             patch.object(llm, "_capable_name", return_value="Claude"):
            result = llm.chat_with_tools(self._msgs(), self._tools())
        cap_mock.assert_called_once()
        self.assertEqual(result, cap_result)

    def test_tools_routing_disabled_uses_legacy(self):
        """routing_enabled=False → _priority_chain_tools() used."""
        llm = _load_llm(_make_cfg(routing_enabled=False))
        legacy_result = {"content": "legacy answer"}
        with patch.object(llm, "_priority_chain_tools", return_value=legacy_result) as legacy_mock:
            result = llm.chat_with_tools(self._msgs(), self._tools())
        legacy_mock.assert_called_once()
        self.assertEqual(result, legacy_result)


# ---------------------------------------------------------------------------
# _capable_name()
# ---------------------------------------------------------------------------

class TestCapableName(unittest.TestCase):

    def test_anthropic_escalation_backend(self):
        llm = _load_llm(_make_cfg(escalation_backend="anthropic", anthropic_api_key="ant-key",
                                  anthropic_model="claude-sonnet-4-6"))
        self.assertIn("Claude", llm._capable_name())

    def test_openai_escalation_backend(self):
        llm = _load_llm(_make_cfg(escalation_backend="openai", openai_api_key="oai-key",
                                  anthropic_api_key="", openai_model="gpt-4o"))
        self.assertIn("GPT", llm._capable_name())

    def test_fallback_to_openai_when_no_anthropic(self):
        llm = _load_llm(_make_cfg(escalation_backend="anthropic", anthropic_api_key="",
                                  openai_api_key="oai-key"))
        self.assertIn("GPT", llm._capable_name())


if __name__ == "__main__":
    unittest.main()
