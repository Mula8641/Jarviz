"""Tests for memory.py — facts CRUD, conversation log, clear."""
import sys
import types
import tempfile
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_memory(db_path: Path):
    """Load memory module with a temp DB path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "memory_test",
        Path(__file__).parent.parent / "memory.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # Patch DB_PATH before exec
    with patch.object(Path, "__new__", lambda cls, *a, **k: object.__new__(cls)):
        pass  # not using this approach

    # Simpler: exec then override DB_PATH
    spec.loader.exec_module(mod)
    mod.DB_PATH = db_path
    # Re-init with the new path
    mod.init()
    return mod


class TestMemoryFacts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self.tmp.name)
        self.mod = _load_memory(self.db_path)

    def tearDown(self):
        self.tmp.close()
        self.db_path.unlink(missing_ok=True)

    def test_set_and_get_fact(self):
        self.mod.set_fact("name", "Alice")
        facts = self.mod.get_facts()
        self.assertIn("name", facts)
        self.assertEqual(facts["name"], "Alice")

    def test_overwrite_fact(self):
        self.mod.set_fact("name", "Alice")
        self.mod.set_fact("name", "Bob")
        facts = self.mod.get_facts()
        self.assertEqual(facts["name"], "Bob")

    def test_clear_facts(self):
        self.mod.set_fact("city", "Berlin")
        self.mod.set_fact("hobby", "coding")
        self.mod.clear_facts()
        facts = self.mod.get_facts()
        self.assertEqual(facts, {})

    def test_delete_fact(self):
        self.mod.set_fact("a", "1")
        self.mod.set_fact("b", "2")
        self.mod.delete_fact("a")
        facts = self.mod.get_facts()
        self.assertNotIn("a", facts)
        self.assertIn("b", facts)

    def test_get_facts_empty(self):
        facts = self.mod.get_facts()
        self.assertEqual(facts, {})

    def test_facts_for_prompt_empty(self):
        result = self.mod.get_facts_for_prompt()
        self.assertEqual(result, "")

    def test_facts_for_prompt_format(self):
        self.mod.set_fact("name", "Alice")
        result = self.mod.get_facts_for_prompt()
        self.assertIn("name", result)
        self.assertIn("Alice", result)
        self.assertIn("-", result)


class TestMemoryConversation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self.tmp.name)
        self.mod = _load_memory(self.db_path)

    def tearDown(self):
        self.tmp.close()
        self.db_path.unlink(missing_ok=True)

    def test_add_and_get_turn(self):
        self.mod.add_turn("user", "Hello!")
        self.mod.add_turn("assistant", "Hi there!")
        conv = self.mod.get_conversation()
        self.assertEqual(len(conv), 2)
        self.assertEqual(conv[0]["role"], "user")
        self.assertEqual(conv[1]["role"], "assistant")

    def test_conversation_limit(self):
        for i in range(10):
            self.mod.add_turn("user", f"msg {i}")
        conv = self.mod.get_conversation(limit=5)
        self.assertEqual(len(conv), 5)

    def test_conversation_order(self):
        self.mod.add_turn("user", "first")
        self.mod.add_turn("assistant", "second")
        self.mod.add_turn("user", "third")
        conv = self.mod.get_conversation()
        self.assertEqual(conv[0]["content"], "first")
        self.assertEqual(conv[-1]["content"], "third")


class TestMemoryKV(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = Path(self.tmp.name)
        self.mod = _load_memory(self.db_path)

    def tearDown(self):
        self.tmp.close()
        self.db_path.unlink(missing_ok=True)

    def test_set_and_get(self):
        self.mod.set("theme", "dark")
        self.assertEqual(self.mod.get("theme"), "dark")

    def test_get_default(self):
        self.assertEqual(self.mod.get("nonexistent", "fallback"), "fallback")

    def test_overwrite(self):
        self.mod.set("key", "v1")
        self.mod.set("key", "v2")
        self.assertEqual(self.mod.get("key"), "v2")


if __name__ == "__main__":
    unittest.main()
