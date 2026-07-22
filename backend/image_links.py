"""
image_links.py — SQLite-backed store linking uploaded chat images to sessions, so a
later text-only follow-up ("what's in that picture?") can look up the most recent
image for that session. Same raw-sqlite3 pattern as local_store.py, kept separate
since this is chat-image lifecycle, not RAG call logs.

No automated cleanup: rows/files are kept indefinitely, matching the existing
unbounded growth of backend/documents/ and rag_logs.db. If disk usage becomes a
concern, a periodic external job could prune rows older than some threshold.
"""
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional

DB_PATH = os.environ.get(
    "IMAGE_LINKS_DB_PATH", os.path.join(os.path.dirname(__file__), "data", "image_links.db")
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
            CREATE TABLE IF NOT EXISTS image_links (
                image_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_image_links_session ON image_links (session_id, created_at DESC)"
        )
    _schema_ready = True


def record_image_link(image_id: str, session_id: str, source_type: str = "user_upload") -> None:
    _ensure_schema()
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO image_links (image_id, session_id, source_type, created_at) VALUES (?, ?, ?, ?)",
            (image_id, session_id, source_type, time.time()),
        )


def get_latest_image_for_session(session_id: str) -> Optional[str]:
    """Returns the most recent image_id uploaded in this session, or None."""
    _ensure_schema()
    with _connect() as conn:
        row = conn.execute(
            "SELECT image_id FROM image_links WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()
    return row["image_id"] if row else None
