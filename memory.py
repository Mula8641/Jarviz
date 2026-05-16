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

# Init on import
init()