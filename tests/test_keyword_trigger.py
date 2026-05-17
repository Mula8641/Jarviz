"""Tests for keyword_trigger.py — phrase matching, cooldown, energy fallback."""
import sys
import types
import time
import unittest
from unittest.mock import MagicMock, patch


def _make_numpy_mock():
    np = MagicMock()
    np.sqrt = __import__("math").sqrt
    np.mean = lambda x: sum(x) / len(x)
    np.clip = lambda a, mn, mx: max(mn, min(float(a[0] if hasattr(a, '__getitem__') else a), mx))
    np.int16 = MagicMock()
    return np


# Patch heavy imports before loading the module
def _load_keyword_trigger():
    import importlib
    # Stub sounddevice
    sd_mock = MagicMock()
    sd_mock.InputStream = MagicMock()
    sys.modules.setdefault("sounddevice", sd_mock)

    # Stub numpy with enough real behaviour
    import numpy as np_real
    sys.modules.setdefault("numpy", np_real)

    # Stub config
    config_mod = types.ModuleType("config")
    config_mod.config = {"keyword_phrase": "hey assistant", "keyword_enabled": True}
    sys.modules["config"] = config_mod

    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "wake.keyword_trigger",
        pathlib.Path(__file__).parent.parent / "wake" / "keyword_trigger.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_keyword_trigger()
KeywordTrigger = mod.KeywordTrigger


class TestKeywordTriggerInit(unittest.TestCase):
    def test_phrase_stored_lowercase(self):
        kt = KeywordTrigger(phrase="Hey Jarviz")
        self.assertEqual(kt.phrase, "hey jarviz")

    def test_update_phrase(self):
        kt = KeywordTrigger(phrase="hello world")
        kt.update_phrase("Good Morning")
        self.assertEqual(kt.phrase, "good morning")

    def test_default_phrase(self):
        kt = KeywordTrigger()
        self.assertEqual(kt.phrase, "hey assistant")

    def test_cooldown_default(self):
        kt = KeywordTrigger()
        self.assertEqual(kt.cooldown, 3.0)

    def test_set_callback(self):
        kt = KeywordTrigger()
        fn = lambda: None
        kt.set_callback(fn)
        self.assertIs(kt.callback, fn)


class TestProcessBufferCooldown(unittest.TestCase):
    """_process_buffer should respect cooldown regardless of STT availability."""

    def _make_kt(self):
        kt = KeywordTrigger(phrase="hey assistant", cooldown=2.0)
        kt.callback = MagicMock()
        return kt

    def test_cooldown_blocks_second_trigger(self):
        kt = self._make_kt()
        import numpy as np

        # Fake audio buffer — silence-level float32 array
        buf = [np.zeros(160, dtype="float32")]

        with patch.object(mod, "_HAS_SR", False):
            kt._process_buffer(buf)
            fired_first = kt.callback.call_count
            kt._process_buffer(buf)  # immediate second call — should be blocked
            fired_second = kt.callback.call_count

        self.assertEqual(fired_first, 1)
        self.assertEqual(fired_second, 1)  # still 1 — cooldown blocked it

    def test_cooldown_allows_after_wait(self):
        kt = self._make_kt()
        import numpy as np
        buf = [np.zeros(160, dtype="float32")]

        with patch.object(mod, "_HAS_SR", False):
            kt._process_buffer(buf)
            kt._last_trigger -= 3.0  # simulate time passing
            kt._process_buffer(buf)

        self.assertEqual(kt.callback.call_count, 2)


class TestProcessBufferSpeechRecognition(unittest.TestCase):
    """_process_buffer with SpeechRecognition available."""

    def _make_kt(self, phrase="hey assistant"):
        kt = KeywordTrigger(phrase=phrase, cooldown=0.0)
        kt.callback = MagicMock()
        return kt

    def test_fires_when_phrase_in_transcript(self):
        kt = self._make_kt("hey assistant")
        import numpy as np

        buf = [np.zeros(160, dtype="float32")]
        sr_mock = MagicMock()
        sr_mock.Recognizer.return_value.recognize_google.return_value = "hey assistant how are you"
        sr_mock.AudioData = MagicMock()
        sr_mock.UnknownValueError = Exception
        sr_mock.RequestError = Exception

        kt._recognizer = sr_mock.Recognizer()

        with patch.object(mod, "_HAS_SR", True), patch.object(mod, "sr", sr_mock):
            kt._process_buffer(buf)

        kt.callback.assert_called_once()

    def test_no_fire_when_phrase_not_in_transcript(self):
        kt = self._make_kt("hey assistant")
        import numpy as np

        buf = [np.zeros(160, dtype="float32")]
        sr_mock = MagicMock()
        sr_mock.Recognizer.return_value.recognize_google.return_value = "what time is it"
        sr_mock.AudioData = MagicMock()
        sr_mock.UnknownValueError = type("UnknownValueError", (Exception,), {})
        sr_mock.RequestError = type("RequestError", (Exception,), {})

        kt._recognizer = sr_mock.Recognizer()

        with patch.object(mod, "_HAS_SR", True), patch.object(mod, "sr", sr_mock):
            kt._process_buffer(buf)

        kt.callback.assert_not_called()

    def test_no_fire_on_unknown_value_error(self):
        kt = self._make_kt("hey assistant")
        import numpy as np

        buf = [np.zeros(160, dtype="float32")]
        UnknownValueError = type("UnknownValueError", (Exception,), {})
        sr_mock = MagicMock()
        sr_mock.Recognizer.return_value.recognize_google.side_effect = UnknownValueError()
        sr_mock.AudioData = MagicMock()
        sr_mock.UnknownValueError = UnknownValueError
        sr_mock.RequestError = type("RequestError", (Exception,), {})

        kt._recognizer = sr_mock.Recognizer()

        with patch.object(mod, "_HAS_SR", True), patch.object(mod, "sr", sr_mock):
            kt._process_buffer(buf)

        kt.callback.assert_not_called()

    def test_energy_fallback_fires(self):
        """Without SR, any speech should trigger callback."""
        kt = self._make_kt("hey assistant")
        import numpy as np
        buf = [np.zeros(160, dtype="float32")]

        with patch.object(mod, "_HAS_SR", False):
            kt._process_buffer(buf)

        kt.callback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
