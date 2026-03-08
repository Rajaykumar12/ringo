"""
rag_logger.py — Azure Table Storage logging for RAG calls.
Logs each query, response, sources, language, and latency to the 'raglogs' table.
Falls back silently if AZURE_STORAGE_CONNECTION_STRING is not configured.
"""
import os
import uuid


def log_rag_call(query: str, response: str, sources: list, language: str, latency_ms: int):
    """Log a RAG call to Azure Table Storage (table: raglogs).

    Uses the same AZURE_STORAGE_CONNECTION_STRING as Blob Storage.
    Table is created automatically on first log if it doesn't exist.
    """
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        return  # Silently skip if not configured

    try:
        from azure.data.tables import TableServiceClient
        from datetime import datetime, timezone

        service = TableServiceClient.from_connection_string(connection_string)
        table = service.create_table_if_not_exists("raglogs")
        entity = {
            "PartitionKey": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "RowKey": str(uuid.uuid4()),
            "query": query[:1000],
            "response": response[:1000],
            "sources": ", ".join(sources),
            "language": language,
            "latency_ms": latency_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        table.upsert_entity(entity)
    except Exception as e:
        print(f"⚠️ Table Storage logging failed: {e}")
