"""
rag_logger.py — RAG call logging.
Logs each query, response, sources, context, and latency to a local
SQLite store (local_store.py) for the admin dashboard.
"""
import logging
import uuid
from datetime import datetime, timezone

from local_store import insert_log, update_log

logger = logging.getLogger("ringo.rag_logger")


def log_rag_call(
    query: str,
    response: str,
    sources: list,
    latency_ms: int,
    context: str = "",
    model_tier: str = "default",
) -> tuple[str, str]:
    """Log a RAG call. Returns (log_id, partition_key)."""
    log_id = str(uuid.uuid4())
    partition_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        insert_log({
            "PartitionKey": partition_key,
            "RowKey": log_id,
            "query": query[:1000],
            "response": response[:1000],
            "sources": ", ".join(sources),
            "latency_ms": latency_ms,
            "context": context[:2000],
            "model_tier": model_tier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"Log insert failed: {e}")

    return log_id, partition_key


def update_eval_scores(log_id: str, partition_key: str, scores: dict):
    """Merge eval scores (faithfulness, answer_relevance, context_relevance) onto an existing row."""
    try:
        update_log(partition_key, log_id, {k: v for k, v in scores.items() if v is not None})
    except Exception as e:
        logger.warning(f"Eval score update failed: {e}")


def log_feedback(log_id: str, partition_key: str, rating: int):
    """Merge a user rating (0 or 1) onto an existing log row."""
    try:
        update_log(partition_key, log_id, {"user_rating": rating})
    except Exception as e:
        logger.warning(f"Feedback logging failed: {e}")
