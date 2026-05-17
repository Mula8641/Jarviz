"""Tests for _get_weather — wttr.in integration via httpx mock."""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_BERLIN_CFG = types.ModuleType("_berlin_cfg")
_BERLIN_CFG.config = {"city": "Berlin"}

import importlib.util
from pathlib import Path


def _setup():
    cfg = types.ModuleType("config")
    cfg.config = {"city": "Berlin"}
    sys.modules["config"] = cfg

    bt_stub = types.ModuleType("browser_tools")
    bt_stub.get_browser = MagicMock()
    bt_stub.shutdown_browser = MagicMock()
    sys.modules.setdefault("browser_tools", bt_stub)


_setup()

spec = importlib.util.spec_from_file_location("tools_wt", Path(__file__).parent.parent / "tools.py")
tools_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools_mod)


MOCK_WEATHER = {
    "current_condition": [{
        "weatherDesc": [{"value": "Partly cloudy"}],
        "temp_C": "18",
        "temp_F": "64",
        "FeelsLikeC": "16",
        "humidity": "65",
        "windspeedKmph": "20",
    }]
}


def _make_http_client(json_data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock(
        side_effect=None if status < 400 else Exception(f"HTTP {status}")
    )
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.get.return_value = resp
    return client


class TestGetWeather(unittest.TestCase):
    def test_returns_temperature_and_description(self):
        with patch.object(tools_mod.httpx, "Client", return_value=_make_http_client(MOCK_WEATHER)):
            result = tools_mod._get_weather("London")
        self.assertIn("Partly cloudy", result)
        self.assertIn("18", result)
        self.assertIn("64", result)

    def test_uses_config_city_when_no_arg(self):
        captured = {}
        real_resp = MagicMock()
        real_resp.raise_for_status.return_value = None
        real_resp.json.return_value = MOCK_WEATHER
        client = _make_http_client(MOCK_WEATHER)
        client.get.side_effect = lambda url, **k: (captured.update({"url": url}), real_resp)[1]
        with patch.object(tools_mod.httpx, "Client", return_value=client), \
             patch.dict(sys.modules, {"config": _BERLIN_CFG}):
            tools_mod._get_weather()
        self.assertIn("Berlin", captured.get("url", ""))

    def test_includes_humidity_and_wind(self):
        with patch.object(tools_mod.httpx, "Client", return_value=_make_http_client(MOCK_WEATHER)):
            result = tools_mod._get_weather("Berlin")
        self.assertIn("65", result)
        self.assertIn("20", result)

    def test_http_error_returns_error_string(self):
        with patch.object(tools_mod.httpx, "Client", return_value=_make_http_client({}, status=503)):
            result = tools_mod._get_weather("Paris")
        self.assertIn("Could not get weather", result)
        self.assertIsInstance(result, str)

    def test_network_exception_returns_error_string(self):
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.get.side_effect = ConnectionError("no network")
        with patch.object(tools_mod.httpx, "Client", return_value=client):
            result = tools_mod._get_weather("Tokyo")
        self.assertIn("Could not get weather", result)

    def test_result_mentions_city(self):
        with patch.object(tools_mod.httpx, "Client", return_value=_make_http_client(MOCK_WEATHER)):
            result = tools_mod._get_weather("Sydney")
        self.assertIn("Sydney", result)


class TestGetWeatherViaExecute(unittest.TestCase):
    def test_execute_routes_to_get_weather(self):
        with patch.object(tools_mod, "_get_weather", return_value="sunny, 20°C") as mock_fn:
            result = tools_mod.execute_tool("get_weather", {"city": "Rome"})
        mock_fn.assert_called_once_with(city="Rome")
        self.assertEqual(result, "sunny, 20°C")

    def test_execute_get_weather_no_args(self):
        with patch.object(tools_mod, "_get_weather", return_value="cloudy") as mock_fn:
            result = tools_mod.execute_tool("get_weather", {})
        mock_fn.assert_called_once_with()
        self.assertEqual(result, "cloudy")


if __name__ == "__main__":
    unittest.main()
