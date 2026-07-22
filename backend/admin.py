"""
admin.py — Read path for the RAG logs already written by rag_logger.py (local_store.py).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from local_store import query_logs

logger = logging.getLogger("ringo.admin")


def _partition_keys_for_days(days: int) -> List[str]:
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def list_logs(days: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
    """Most recent log entries across the last `days` partitions, newest first."""
    entities = query_logs(_partition_keys_for_days(days))
    entities.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return entities[:limit]


def get_stats(days: int = 7) -> Dict[str, Any]:
    """Aggregate stats over the last `days` days: volume, latency, ratings, eval scores."""
    entities = query_logs(_partition_keys_for_days(days))

    total = len(entities)
    if total == 0:
        return {"total_calls": 0}

    latencies = [e["latency_ms"] for e in entities if e.get("latency_ms") is not None]
    ratings = [e["user_rating"] for e in entities if e.get("user_rating") is not None]
    faithfulness = [e["faithfulness"] for e in entities if e.get("faithfulness") is not None]
    answer_relevance = [e["answer_relevance"] for e in entities if e.get("answer_relevance") is not None]
    context_relevance = [e["context_relevance"] for e in entities if e.get("context_relevance") is not None]

    def avg(values: List[float]) -> Optional[float]:
        return round(sum(values) / len(values), 3) if values else None

    return {
        "total_calls": total,
        "avg_latency_ms": avg(latencies),
        "thumbs_up": sum(1 for r in ratings if r == 1),
        "thumbs_down": sum(1 for r in ratings if r == 0),
        "avg_faithfulness": avg(faithfulness),
        "avg_answer_relevance": avg(answer_relevance),
        "avg_context_relevance": avg(context_relevance),
    }
