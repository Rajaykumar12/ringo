"""
local_store.py — SQLite-backed store for RAG call logs, read by admin.py for the
admin dashboard and written by rag_logger.py after every chat call.
"""
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List

DB_PATH = os.environ.get(
    "LOCAL_LOGS_DB_PATH", os.path.join(os.path.dirname(__file__), "data", "rag_logs.db")
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
            CREATE TABLE IF NOT EXISTS raglogs (
                partition_key TEXT NOT NULL,
                row_key TEXT NOT NULL,
                query TEXT,
                response TEXT,
                sources TEXT,
                language TEXT,
                latency_ms INTEGER,
                context TEXT,
                model_tier TEXT,
                timestamp TEXT,
                user_rating INTEGER,
                faithfulness REAL,
                answer_relevance REAL,
                context_relevance REAL,
                PRIMARY KEY (partition_key, row_key)
            )
            """
        )
    _schema_ready = True


def insert_log(entity: Dict[str, Any]) -> None:
    _ensure_schema()
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO raglogs
               (partition_key, row_key, query, response, sources, language, latency_ms, context, model_tier, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity["PartitionKey"], entity["RowKey"], entity.get("query"), entity.get("response"),
                entity.get("sources"), entity.get("language"), entity.get("latency_ms"),
                entity.get("context"), entity.get("model_tier"), entity.get("timestamp"),
            ),
        )


def update_log(partition_key: str, row_key: str, updates: Dict[str, Any]) -> None:
    _ensure_schema()
    if not updates:
        return
    cols = ", ".join(f"{key} = ?" for key in updates)
    with _connect() as conn:
        conn.execute(
            f"UPDATE raglogs SET {cols} WHERE partition_key = ? AND row_key = ?",
            (*updates.values(), partition_key, row_key),
        )


def query_logs(partitions: List[str]) -> List[Dict[str, Any]]:
    _ensure_schema()
    placeholders = ", ".join("?" for _ in partitions)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM raglogs WHERE partition_key IN ({placeholders}) ORDER BY timestamp DESC",
            partitions,
        ).fetchall()

    entities = []
    for row in rows:
        entity = dict(row)
        entity["PartitionKey"] = entity.pop("partition_key")
        entity["RowKey"] = entity.pop("row_key")
        entities.append(entity)
    return entities
