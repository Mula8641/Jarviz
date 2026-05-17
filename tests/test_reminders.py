"""Tests for reminder memory functions and remind_me / list_reminders tools."""
import sys
import types
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import importlib.util


# ── Load memory module with temp DB ─────────────────────────────────────────
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_mem_spec = importlib.util.spec_from_file_location(
    "memory_rem", Path(__file__).parent.parent / "memory.py"
)
mem_mod = importlib.util.module_from_spec(_mem_spec)
_mem_spec.loader.exec_module(mem_mod)
mem_mod.DB_PATH = Path(_tmp.name)
mem_mod.init()
sys.modules["memory"] = mem_mod


# ── Load tools module ────────────────────────────────────────────────────────
_cfg = types.ModuleType("config")
_cfg.config = {"city": "Berlin"}
sys.modules["config"] = _cfg

bt_stub = types.ModuleType("browser_tools")
bt_stub.get_browser = MagicMock()
bt_stub.shutdown_browser = MagicMock()
sys.modules.setdefault("browser_tools", bt_stub)

_tspec = importlib.util.spec_from_file_location(
    "tools_rem", Path(__file__).parent.parent / "tools.py"
)
tools_mod = importlib.util.module_from_spec(_tspec)
_tspec.loader.exec_module(tools_mod)


# ── Helper ───────────────────────────────────────────────────────────────────
def _clear_reminders():
    # Re-anchor sys.modules["memory"] to our temp-DB module so tools_mod lazy
    # imports pick up the right DB even if another test file changed the pointer.
    sys.modules["memory"] = mem_mod
    import sqlite3
    with sqlite3.connect(mem_mod.DB_PATH) as conn:
        conn.execute("DELETE FROM reminders")


class TestParseReminderTime(unittest.TestCase):
    def _parse(self, s):
        return tools_mod._parse_reminder_time(s)

    def test_in_minutes(self):
        before = datetime.utcnow()
        result = self._parse("in 10 minutes")
        self.assertAlmostEqual((result - before).total_seconds(), 600, delta=5)

    def test_in_minutes_short(self):
        before = datetime.utcnow()
        result = self._parse("in 30 mins")
        self.assertAlmostEqual((result - before).total_seconds(), 1800, delta=5)

    def test_in_hours(self):
        before = datetime.utcnow()
        result = self._parse("in 2 hours")
        self.assertAlmostEqual((result - before).total_seconds(), 7200, delta=5)

    def test_in_seconds(self):
        before = datetime.utcnow()
        result = self._parse("in 5 seconds")
        self.assertAlmostEqual((result - before).total_seconds(), 5, delta=2)

    def test_at_pm_time(self):
        result = self._parse("at 3pm")
        # hour should be 15
        self.assertEqual(result.hour, 15)
        self.assertEqual(result.minute, 0)

    def test_at_time_with_minutes(self):
        result = self._parse("at 14:30")
        self.assertEqual(result.hour, 14)
        self.assertEqual(result.minute, 30)

    def test_at_12pm_noon(self):
        result = self._parse("at 12pm")
        self.assertEqual(result.hour, 12)

    def test_at_12am_midnight(self):
        result = self._parse("at 12am")
        self.assertEqual(result.hour, 0)

    def test_at_9am(self):
        result = self._parse("at 9am")
        self.assertEqual(result.hour, 9)

    def test_tomorrow(self):
        result = self._parse("tomorrow")
        tomorrow = (datetime.utcnow() + timedelta(days=1)).date()
        self.assertEqual(result.date(), tomorrow)
        self.assertEqual(result.hour, 9)  # default

    def test_tomorrow_at_specific_time(self):
        result = self._parse("tomorrow at 8am")
        tomorrow = (datetime.utcnow() + timedelta(days=1)).date()
        self.assertEqual(result.date(), tomorrow)
        self.assertEqual(result.hour, 8)

    def test_invalid_raises_value_error(self):
        with self.assertRaises(ValueError):
            self._parse("next week sometime")


class TestReminderMemoryFunctions(unittest.TestCase):
    def setUp(self):
        _clear_reminders()

    def test_add_reminder_returns_id(self):
        future_iso = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        rid = mem_mod.add_reminder("Call John", future_iso)
        self.assertIsInstance(rid, int)
        self.assertGreater(rid, 0)

    def test_get_upcoming_returns_future_reminders(self):
        future_iso = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        mem_mod.add_reminder("Meeting", future_iso)
        upcoming = mem_mod.get_upcoming_reminders()
        self.assertEqual(len(upcoming), 1)
        self.assertEqual(upcoming[0]["message"], "Meeting")

    def test_get_due_returns_past_reminders(self):
        past_iso = (datetime.utcnow() - timedelta(seconds=5)).isoformat()
        mem_mod.add_reminder("Past reminder", past_iso)
        due = mem_mod.get_due_reminders()
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["message"], "Past reminder")

    def test_future_not_in_due(self):
        future_iso = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        mem_mod.add_reminder("Future", future_iso)
        due = mem_mod.get_due_reminders()
        self.assertEqual(len(due), 0)

    def test_mark_reminder_done_removes_from_due(self):
        past_iso = (datetime.utcnow() - timedelta(seconds=5)).isoformat()
        rid = mem_mod.add_reminder("Do thing", past_iso)
        mem_mod.mark_reminder_done(rid)
        due = mem_mod.get_due_reminders()
        self.assertEqual(len(due), 0)

    def test_mark_done_also_removed_from_upcoming(self):
        future_iso = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        rid = mem_mod.add_reminder("Future task", future_iso)
        mem_mod.mark_reminder_done(rid)
        upcoming = mem_mod.get_upcoming_reminders()
        self.assertEqual(len(upcoming), 0)

    def test_multiple_reminders_ordered_by_time(self):
        t1 = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        t2 = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        mem_mod.add_reminder("Later", t1)
        mem_mod.add_reminder("Sooner", t2)
        upcoming = mem_mod.get_upcoming_reminders()
        self.assertEqual(upcoming[0]["message"], "Sooner")
        self.assertEqual(upcoming[1]["message"], "Later")

    def test_due_reminders_include_id_message_remind_at(self):
        past_iso = (datetime.utcnow() - timedelta(seconds=1)).isoformat()
        mem_mod.add_reminder("Check email", past_iso)
        due = mem_mod.get_due_reminders()
        self.assertIn("id", due[0])
        self.assertIn("message", due[0])
        self.assertIn("remind_at", due[0])


class TestRemindMeTool(unittest.TestCase):
    def setUp(self):
        _clear_reminders()
        sys.modules["memory"] = mem_mod

    def test_remind_me_returns_confirmation(self):
        result = tools_mod._remind_me("call dentist", "in 30 minutes")
        self.assertIn("call dentist", result)
        self.assertIn("Reminder", result)

    def test_remind_me_stores_in_db(self):
        tools_mod._remind_me("take pill", "in 1 hour")
        upcoming = mem_mod.get_upcoming_reminders()
        messages = [r["message"] for r in upcoming]
        self.assertIn("take pill", messages)

    def test_remind_me_invalid_time_returns_error(self):
        result = tools_mod._remind_me("do thing", "whenever")
        self.assertIn("Cannot parse", result)

    def test_remind_me_returns_reminder_id(self):
        result = tools_mod._remind_me("water plants", "in 2 hours")
        self.assertIn("#", result)

    def test_execute_tool_routes_remind_me(self):
        with patch.object(tools_mod, "_remind_me", return_value="Reminder #1 set") as mock_fn:
            result = tools_mod.execute_tool("remind_me", {"message": "eat lunch", "when": "in 1 hour"})
        mock_fn.assert_called_once_with(message="eat lunch", when="in 1 hour")
        self.assertEqual(result, "Reminder #1 set")


class TestListRemindersTool(unittest.TestCase):
    def setUp(self):
        _clear_reminders()
        sys.modules["memory"] = mem_mod

    def test_empty_returns_no_upcoming(self):
        result = tools_mod._list_reminders()
        self.assertIn("No upcoming", result)

    def test_shows_pending_reminders(self):
        future_iso = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        mem_mod.add_reminder("Read book", future_iso)
        result = tools_mod._list_reminders()
        self.assertIn("Read book", result)

    def test_does_not_show_done_reminders(self):
        future_iso = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        rid = mem_mod.add_reminder("Done thing", future_iso)
        mem_mod.mark_reminder_done(rid)
        result = tools_mod._list_reminders()
        self.assertNotIn("Done thing", result)

    def test_execute_tool_routes_list_reminders(self):
        with patch.object(tools_mod, "_list_reminders", return_value="No upcoming reminders.") as mock_fn:
            tools_mod.execute_tool("list_reminders", {})
        mock_fn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
