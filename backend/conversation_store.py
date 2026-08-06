"""
conversation_store.py — SQLite-backed durable conversation history.

memory.py treats Redis/in-memory as a hot-path cache (TTL'd or process-local);
this module is the write-through backing store so a conversation survives a
Redis eviction or a backend restart. Mirrors local_store.py's connection/schema
pattern (own DB file, no new dependency).
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List

DB_PATH = os.environ.get(
    "CONVERSATIONS_DB_PATH", os.path.join(os.path.dirname(__file__), "data", "conversations.db")
)

_schema_ready = False


@contextmanager
def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id, id)"
        )
    _schema_ready = True


def append_message(session_id: str, role: str, content: str) -> None:
    """Persist one turn. role is 'human' or 'ai', matching langchain_core message types."""
    _ensure_schema()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now(timezone.utc).isoformat()),
        )


def get_messages(session_id: str) -> List[Dict[str, Any]]:
    """Full persisted history for a session, oldest first."""
    _ensure_schema()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def clear_session(session_id: str) -> None:
    _ensure_schema()
    with _connect() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
