"""SQLite memory layer — persistent, evolvable conversation storage."""
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger("memory")

DB_PATH = Path(__file__).parent / "memory.db"

def init():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                source TEXT DEFAULT 'extracted',
                updated_at TEXT NOT NULL
            )
        """)
        log.info("Memory DB initialized at %s", DB_PATH)

def set(key: str, value: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO memory (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.utcnow().isoformat()),
        )

def get(key: str, default: str = "") -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT value FROM memory WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

def add_turn(role: str, content: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO conversation (role, content, created_at) VALUES (?, ?, ?)",
            (role, content, datetime.utcnow().isoformat()),
        )

def get_conversation(limit: int = 50) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversation ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

# --- User Facts (cross-session memory) ---

def set_fact(key: str, value: str, source: str = "extracted"):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_facts (key, value, source, updated_at) VALUES (?, ?, ?, ?)",
            (key, value, source, datetime.utcnow().isoformat()),
        )

def get_facts() -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT key, value FROM user_facts").fetchall()
        return {r[0]: r[1] for r in rows}

def extract_and_store_facts(conversation: list[dict]):
    """Use LLM to extract key facts from conversation and store them."""
    from llm import chat as llm_chat
    if not conversation:
        return
    conv_text = "\n".join(f"{m['role']}: {m['content']}" for m in conversation[-20:])
    prompt = f"""Extract 1-3 short personal facts from this conversation.
Return ONLY a JSON object like: {{"fact_key": "fact value"}}
Facts should be about: user preferences, habits, names, important context.
If nothing notable, return {{}}.

Conversation:
{conv_text}"""
    try:
        result = llm_chat([{"role": "user", "content": prompt}])
        import json
        import re
        match = re.search(r'\{[^{}]+\}', result)
        if match:
            facts = json.loads(match.group())
            for key, value in facts.items():
                set_fact(key, str(value))
                log.info("Stored fact: %s = %s", key, value)
    except Exception as e:
        log.warning("Fact extraction failed: %s", e)

def clear_facts():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM user_facts")
    log.info("All user facts cleared")

def delete_fact(key: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM user_facts WHERE key = ?", (key,))
    log.info("Fact deleted: %s", key)

def get_facts_for_prompt() -> str:
    facts = get_facts()
    if not facts:
        return ""
    lines = [f"- {k}: {v}" for k, v in facts.items()]
    return "\n".join(lines)

# Init on import
init()