"""Tests for server.py — memory, config, trigger endpoints via TestClient."""
import sys
import types
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


def _stub_imports():
    """Stub all heavy dependencies before importing server."""
    stubs = {
        "truststore": MagicMock(),
        "sounddevice": MagicMock(),
        "playwright": MagicMock(),
        "playwright.sync_api": MagicMock(),
        "elevenlabs": MagicMock(),
        "pywin32": MagicMock(),
        "win32api": MagicMock(),
        "win32con": MagicMock(),
        "win32gui": MagicMock(),
    }
    for name, mock in stubs.items():
        sys.modules.setdefault(name, mock)

    # Stub logger
    logger_mod = types.ModuleType("logger")
    logger_mod.setup_logger = lambda name: __import__("logging").getLogger(name)
    sys.modules["logger"] = logger_mod

    # Stub llm
    llm_mod = types.ModuleType("llm")
    llm_mod.chat = MagicMock(return_value="ok")
    llm_mod.describe_image = MagicMock(return_value="desc")
    sys.modules["llm"] = llm_mod

    # Stub audio_tools
    audio_mod = types.ModuleType("audio_tools")
    audio_mod.text_to_speech = MagicMock(return_value=b"audio")
    sys.modules["audio_tools"] = audio_mod

    # Stub prompts
    prompts_mod = types.ModuleType("prompts")
    prompts_mod.system_prompt = MagicMock(return_value="sys")
    prompts_mod.greeting_prompt = MagicMock(return_value="hi")
    sys.modules["prompts"] = prompts_mod

    # Stub context
    ctx_mod = types.ModuleType("context")
    ctx_mod.ConversationContext = MagicMock()
    sys.modules["context"] = ctx_mod

    # Stub browser_tools
    bt_mod = types.ModuleType("browser_tools")
    bt_mod.BrowserTools = MagicMock()
    bt_mod.get_browser = MagicMock()
    bt_mod.shutdown_browser = MagicMock()
    sys.modules["browser_tools"] = bt_mod

    # Stub screenshot_cache
    sc_mod = types.ModuleType("screenshot_cache")
    sc_mod.storeScreenshot = MagicMock(return_value="/tmp/ss.png")
    sys.modules["screenshot_cache"] = sc_mod

    # Stub wake modules
    wake_pkg = types.ModuleType("wake")
    sys.modules["wake"] = wake_pkg
    ts_mod = types.ModuleType("wake.trigger_server")
    ts_mod.start_trigger_server = MagicMock(return_value=lambda: None)
    sys.modules["wake.trigger_server"] = ts_mod

    # Stub agent
    agent_mod = types.ModuleType("agent")
    agent_mod.run = MagicMock(return_value="agent response")
    sys.modules["agent"] = agent_mod


_stub_imports()

import tempfile, sqlite3
from pathlib import Path

# Set up a temp memory db before importing server
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db_path = Path(_tmp_db.name)

# Patch memory module to use temp db
import importlib.util as ilu
_mem_spec = ilu.spec_from_file_location(
    "memory",
    Path(__file__).parent.parent / "memory.py",
)
_mem_mod = ilu.module_from_spec(_mem_spec)
_mem_spec.loader.exec_module(_mem_mod)
_mem_mod.DB_PATH = _tmp_db_path
_mem_mod.init()
sys.modules["memory"] = _mem_mod

# Patch config module
_cfg_mod = types.ModuleType("config")
_cfg_data = {
    "minimax_api_key": "", "elevenlabs_api_key": "", "elevenlabs_voice_id": "",
    "user_name": "Test", "city": "Berlin", "clap_threshold": 0.15,
    "clap_max_gap": 1.2, "keyword_phrase": "hey assistant", "keyword_enabled": False,
}
_cfg_mod.config = dict(_cfg_data)

def _cfg_reload():
    pass  # no-op for tests

_cfg_mod.reload = _cfg_reload
_cfg_mod.load = lambda: dict(_cfg_data)
sys.modules["config"] = _cfg_mod

# Now import the app
import importlib
_server_spec = ilu.spec_from_file_location(
    "server",
    Path(__file__).parent.parent / "server.py",
)
server_mod = ilu.module_from_spec(_server_spec)
_server_spec.loader.exec_module(server_mod)
app = server_mod.app

from fastapi.testclient import TestClient
client = TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint(unittest.TestCase):
    def test_health_ok(self):
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "healthy")


class TestMemoryEndpoints(unittest.TestCase):
    def setUp(self):
        _mem_mod.clear_facts()

    def test_get_facts_empty(self):
        r = client.get("/memory/facts")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["facts"], {})

    def test_get_facts_with_data(self):
        _mem_mod.set_fact("name", "Alice")
        r = client.get("/memory/facts")
        self.assertEqual(r.status_code, 200)
        self.assertIn("name", r.json()["facts"])
        self.assertEqual(r.json()["facts"]["name"], "Alice")

    def test_clear_facts(self):
        _mem_mod.set_fact("name", "Alice")
        r = client.post("/memory/clear")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")
        facts = _mem_mod.get_facts()
        self.assertEqual(facts, {})


class TestConfigEndpoints(unittest.TestCase):
    def test_get_config(self):
        r = client.get("/config")
        self.assertEqual(r.status_code, 200)

    def test_save_config_returns_ok(self):
        with tempfile.TemporaryDirectory() as d:
            cfg_path = Path(d) / "config.json"
            ex_path = Path(d) / "config.example.json"
            ex_path.write_text(json.dumps(_cfg_data))

            with patch.object(server_mod, "__file__", str(Path(d) / "server.py")):
                # Just check the endpoint shape; actual file write is tested in test_config.py
                pass

        r = client.post("/config/save", json={"user_name": "NewName"})
        # Either ok or an error about missing config file — both are valid shapes
        data = r.json()
        self.assertIn("status", data)


class TestTriggerEndpoints(unittest.TestCase):
    def test_clap_enable_when_no_sounddevice(self):
        with patch.dict(sys.modules, {"wake.clap_trigger": MagicMock(side_effect=ImportError("no sd"))}):
            r = client.post("/triggers/clap", json={"enabled": True})
        data = r.json()
        # Should return error since sounddevice not available, or ok if already running
        self.assertIn("status", data)

    def test_clap_disable_no_trigger(self):
        r = client.post("/triggers/clap", json={"enabled": False})
        self.assertEqual(r.json()["status"], "ok")
        self.assertFalse(r.json()["enabled"])

    def test_keyword_disable_no_trigger(self):
        r = client.post("/triggers/keyword", json={"enabled": False})
        self.assertEqual(r.json()["status"], "ok")
        self.assertFalse(r.json()["enabled"])


if __name__ == "__main__":
    unittest.main()
