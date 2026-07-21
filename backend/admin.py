"""
admin.py — Read path for the RAG logs already written by rag_logger.py.
Reads from Azure Table Storage ('raglogs') when configured, otherwise from the
local SQLite fallback (local_store.py) used in local dev.
"""
import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ringo.admin")


def _get_table():
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        return None
    from azure.data.tables import TableServiceClient

    service = TableServiceClient.from_connection_string(connection_string)
    return service.get_table_client("raglogs")


def _partition_keys_for_days(days: int) -> List[str]:
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def _query_entities(days: int) -> List[Dict[str, Any]]:
    """Fetch raw log entities from whichever backing store is active."""
    partitions = _partition_keys_for_days(days)
    table = _get_table()
    if table is None:
        from local_store import query_logs

        return query_logs(partitions)

    filter_expr = " or ".join(f"PartitionKey eq '{pk}'" for pk in partitions)
    return [dict(e) for e in table.query_entities(filter_expr)]


def list_logs(days: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
    """Most recent log entries across the last `days` partitions, newest first."""
    entities = _query_entities(days)
    entities.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return entities[:limit]


def get_stats(days: int = 7) -> Dict[str, Any]:
    """Aggregate stats over the last `days` days: volume, latency, ratings, eval scores, languages."""
    entities = _query_entities(days)

    total = len(entities)
    if total == 0:
        return {"configured": True, "total_calls": 0}

    latencies = [e["latency_ms"] for e in entities if e.get("latency_ms") is not None]
    ratings = [e["user_rating"] for e in entities if e.get("user_rating") is not None]
    faithfulness = [e["faithfulness"] for e in entities if e.get("faithfulness") is not None]
    answer_relevance = [e["answer_relevance"] for e in entities if e.get("answer_relevance") is not None]
    context_relevance = [e["context_relevance"] for e in entities if e.get("context_relevance") is not None]
    languages = Counter(e.get("language", "unknown") for e in entities)

    def avg(values: List[float]) -> Optional[float]:
        return round(sum(values) / len(values), 3) if values else None

    return {
        "configured": True,
        "total_calls": total,
        "avg_latency_ms": avg(latencies),
        "thumbs_up": sum(1 for r in ratings if r == 1),
        "thumbs_down": sum(1 for r in ratings if r == 0),
        "avg_faithfulness": avg(faithfulness),
        "avg_answer_relevance": avg(answer_relevance),
        "avg_context_relevance": avg(context_relevance),
        "language_breakdown": dict(languages),
    }
