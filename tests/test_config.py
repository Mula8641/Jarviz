"""Tests for config.py — load, env override, reload."""
import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_config_module(config_path: Path, example_path: Path):
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "config_test_" + str(id(config_path)),
        Path(__file__).parent.parent / "config.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # Patch paths before exec
    mod_patches = {
        "CONFIG_PATH": config_path,
        "_example": example_path,
    }
    spec.loader.exec_module(mod)
    mod.CONFIG_PATH = config_path
    mod._example = example_path
    # Re-run load()
    mod.config = mod.load()
    return mod


class TestConfigLoad(unittest.TestCase):
    def _write(self, path, data):
        with open(path, "w") as f:
            json.dump(data, f)

    def test_loads_from_config_json(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "config.json"
            ex = Path(d) / "config.example.json"
            self._write(cfg, {"user_name": "Alice", "city": "London"})
            self._write(ex, {"user_name": "Default"})
            mod = _load_config_module(cfg, ex)
            self.assertEqual(mod.config["user_name"], "Alice")

    def test_falls_back_to_example_when_no_config(self):
        with tempfile.TemporaryDirectory() as d:
            ex = Path(d) / "config.example.json"
            missing = Path(d) / "config.json"
            self._write(ex, {"user_name": "ExampleUser", "city": "Paris"})
            mod = _load_config_module(missing, ex)
            self.assertEqual(mod.config["user_name"], "ExampleUser")

    def test_env_override_wins(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "config.json"
            ex = Path(d) / "config.example.json"
            self._write(cfg, {"user_name": "Alice", "city": "London"})
            self._write(ex, {})
            with patch.dict(os.environ, {"USER_NAME": "EnvUser", "CITY": "Tokyo"}):
                mod = _load_config_module(cfg, ex)
            self.assertEqual(mod.config["user_name"], "EnvUser")
            self.assertEqual(mod.config["city"], "Tokyo")

    def test_clap_threshold_type(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "config.json"
            ex = Path(d) / "config.example.json"
            self._write(cfg, {"clap_threshold": 0.25})
            self._write(ex, {})
            mod = _load_config_module(cfg, ex)
            self.assertIsInstance(mod.config["clap_threshold"], float)
            self.assertAlmostEqual(mod.config["clap_threshold"], 0.25)

    def test_keyword_enabled_bool_from_env(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "config.json"
            ex = Path(d) / "config.example.json"
            self._write(cfg, {"keyword_enabled": False})
            self._write(ex, {})
            with patch.dict(os.environ, {"KEYWORD_ENABLED": "true"}):
                mod = _load_config_module(cfg, ex)
            self.assertTrue(mod.config["keyword_enabled"])


class TestConfigReload(unittest.TestCase):
    def _write(self, path, data):
        with open(path, "w") as f:
            json.dump(data, f)

    def test_reload_picks_up_new_values(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "config.json"
            ex = Path(d) / "config.example.json"
            self._write(cfg, {"user_name": "Before", "city": "Berlin"})
            self._write(ex, {})
            mod = _load_config_module(cfg, ex)
            self.assertEqual(mod.config["user_name"], "Before")

            # Simulate UI save — update file
            self._write(cfg, {"user_name": "After", "city": "Berlin"})
            mod.reload()

            self.assertEqual(mod.config["user_name"], "After")

    def test_reload_updates_in_place(self):
        """Config dict identity must be preserved so all importers see the change."""
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "config.json"
            ex = Path(d) / "config.example.json"
            self._write(cfg, {"user_name": "X", "city": "C"})
            self._write(ex, {})
            mod = _load_config_module(cfg, ex)
            original_id = id(mod.config)
            self._write(cfg, {"user_name": "Y", "city": "C"})
            mod.reload()
            self.assertEqual(id(mod.config), original_id)


if __name__ == "__main__":
    unittest.main()
