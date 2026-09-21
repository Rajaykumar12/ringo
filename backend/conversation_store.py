"""
conversation_store.py — SQLite-backed durable conversation history.

memory.py treats Redis/in-memory as a hot-path cache (TTL'd or process-local);
this module is the write-through backing store so a conversation survives a
Redis eviction or a backend restart. Mirrors local_store.py's connection/schema
pattern (own DB file, no new dependency).
"""
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

DB_PATH = os.environ.get(
    "CONVERSATIONS_DB_PATH", os.path.join(os.path.dirname(__file__), "data", "conversations.db")
)

_schema_ready = False

# One SQLite connection per thread, reused across calls, instead of a fresh
# connect/close (plus an os.makedirs) on every single operation. WAL mode lets
# readers and the writer proceed concurrently — these stores are called from
# asyncio.to_thread workers and BackgroundTasks at the same time, and the
# default DELETE journal serialises them into "database is locked" under load.
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is not None and getattr(_local, "path", None) == DB_PATH:
        return conn
    if conn is not None:  # DB_PATH changed (tests/env) — rebind this thread
        conn.close()
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # safe under WAL, far fewer fsyncs
    _local.conn = conn
    _local.path = DB_PATH
    return conn


@contextmanager
def _connect():
    """Yields this thread's connection; commits on clean exit, rolls back on error."""
    conn = _get_conn()
    with conn:
        yield conn


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
    append_messages(session_id, [(role, content)])


def append_messages(session_id: str, rows: List[Tuple[str, str]]) -> None:
    """Persist several turns in one statement/transaction. memory.py writes a whole
    add_messages batch at once, so this avoids a separate round-trip per message."""
    if not rows:
        return
    _ensure_schema()
    timestamp = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            [(session_id, role, content, timestamp) for role, content in rows],
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
