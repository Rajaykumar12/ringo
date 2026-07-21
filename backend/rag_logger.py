"""
rag_logger.py — RAG call logging.
Logs each query, response, sources, context, language, and latency to the 'raglogs' table
in Azure Table Storage when AZURE_STORAGE_CONNECTION_STRING is configured (production);
otherwise falls back to a local SQLite store (local_store.py) so logs/admin stats still
work in local dev.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("ringo.rag_logger")


def log_rag_call(
    query: str,
    response: str,
    sources: list,
    language: str,
    latency_ms: int,
    context: str = "",
    model_tier: str = "default",
) -> tuple[str, str]:
    """Log a RAG call. Returns (log_id, partition_key) — even when Azure is not configured."""
    log_id = str(uuid.uuid4())
    partition_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        from local_store import insert_log

        try:
            insert_log({
                "PartitionKey": partition_key,
                "RowKey": log_id,
                "query": query[:1000],
                "response": response[:1000],
                "sources": ", ".join(sources),
                "language": language,
                "latency_ms": latency_ms,
                "context": context[:2000],
                "model_tier": model_tier,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.warning(f"Local log insert failed: {e}")
        return log_id, partition_key

    try:
        from azure.data.tables import TableServiceClient

        service = TableServiceClient.from_connection_string(connection_string)
        table = service.create_table_if_not_exists("raglogs")
        entity = {
            "PartitionKey": partition_key,
            "RowKey": log_id,
            "query": query[:1000],
            "response": response[:1000],
            "sources": ", ".join(sources),
            "language": language,
            "latency_ms": latency_ms,
            "context": context[:2000],
            "model_tier": model_tier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        table.upsert_entity(entity)
    except Exception as e:
        logger.warning(f"Table Storage logging failed: {e}")

    return log_id, partition_key


def update_eval_scores(log_id: str, partition_key: str, scores: dict):
    """Merge eval scores (faithfulness, answer_relevance, context_relevance) onto an existing row."""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        from local_store import update_log

        try:
            update_log(partition_key, log_id, {k: v for k, v in scores.items() if v is not None})
        except Exception as e:
            logger.warning(f"Local eval score update failed: {e}")
        return

    try:
        from azure.data.tables import TableServiceClient, UpdateMode

        service = TableServiceClient.from_connection_string(connection_string)
        table = service.get_table_client("raglogs")
        entity = {"PartitionKey": partition_key, "RowKey": log_id}
        for key, val in scores.items():
            if val is not None:
                entity[key] = val
        table.update_entity(entity, mode=UpdateMode.MERGE)
    except Exception as e:
        logger.warning(f"Eval score update failed: {e}")


def log_feedback(log_id: str, partition_key: str, rating: int):
    """Merge a user rating (0 or 1) onto an existing log row."""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        from local_store import update_log

        try:
            update_log(partition_key, log_id, {"user_rating": rating})
        except Exception as e:
            logger.warning(f"Local feedback logging failed: {e}")
        return

    try:
        from azure.data.tables import TableServiceClient, UpdateMode

        service = TableServiceClient.from_connection_string(connection_string)
        table = service.get_table_client("raglogs")
        entity = {
            "PartitionKey": partition_key,
            "RowKey": log_id,
            "user_rating": rating,
        }
        table.update_entity(entity, mode=UpdateMode.MERGE)
    except Exception as e:
        logger.warning(f"Feedback logging failed: {e}")
