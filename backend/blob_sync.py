"""
blob_sync.py — Azure Blob Storage document sync.
Downloads documents from a configured Azure Blob container to local folder.
Falls back to local documents/ folder if Azure is not configured.
"""
import logging
import os

logger = logging.getLogger("ringo.blob_sync")

ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".md"}
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 20 * 1024 * 1024))  # 20 MB default


def sync_documents_from_blob(local_folder: str = "documents"):
    """Download documents from Azure Blob Storage to local folder.

    Requires env vars:
    - AZURE_STORAGE_CONNECTION_STRING: From Azure Portal → Storage Account → Access keys
    - AZURE_STORAGE_CONTAINER_NAME: Blob container name (default: 'documents')

    Falls back to local documents/ folder if not configured (for local dev).
    """
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "documents")

    if not connection_string:
        logger.info("AZURE_STORAGE_CONNECTION_STRING not set - using local documents/ folder")
        return

    try:
        from azure.storage.blob import ContainerClient

        os.makedirs(local_folder, exist_ok=True)
        container_client = ContainerClient.from_connection_string(connection_string, container_name)

        blob_list = list(container_client.list_blobs())
        # Use basename for comparison — blob paths may contain subdirectory separators
        blob_basenames = {os.path.basename(blob.name) for blob in blob_list}
        logger.info(f"Found {len(blob_list)} file(s) in Azure Blob Storage '{container_name}'")

        # Delete local files that no longer exist in blob storage
        if os.path.exists(local_folder):
            for local_file in os.listdir(local_folder):
                if local_file not in blob_basenames:
                    local_path = os.path.join(local_folder, local_file)
                    logger.info(f"Deleting orphaned file: {local_file}")
                    os.remove(local_path)

        for blob in blob_list:
            safe_name = os.path.basename(blob.name)
            if not safe_name:
                continue
            local_path = os.path.join(local_folder, safe_name)
            if os.path.exists(local_path) and os.path.getsize(local_path) == blob.size:
                logger.debug(f"Already up to date: {safe_name}")
                continue
            logger.info(f"Downloading: {safe_name} ({blob.size} bytes)")
            blob_data = container_client.download_blob(blob.name).readall()
            with open(local_path, "wb") as f:
                f.write(blob_data)

        logger.info("Azure Blob Storage sync complete")
    except Exception as e:
        logger.warning(f"Azure Blob sync failed: {e}. Falling back to local documents/")


def upload_document(filename: str, data: bytes, local_folder: str = "documents") -> None:
    """Upload a document to Azure Blob Storage (or local folder if Azure not configured)."""
    # Sanitize filename — strip any path components
    safe_name = os.path.basename(filename)
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File too large ({len(data)} bytes). Maximum is {MAX_UPLOAD_BYTES // (1024*1024)} MB.")

    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "documents")

    if connection_string:
        try:
            from azure.storage.blob import BlobServiceClient
            client = BlobServiceClient.from_connection_string(connection_string)
            blob_client = client.get_blob_client(container=container_name, blob=safe_name)
            blob_client.upload_blob(data, overwrite=True)
            logger.info(f"Uploaded '{safe_name}' to Azure Blob Storage '{container_name}'")
            return
        except Exception as e:
            logger.warning(f"Azure upload failed: {e}. Saving locally instead.")

    # Local fallback
    os.makedirs(local_folder, exist_ok=True)
    with open(os.path.join(local_folder, safe_name), "wb") as f:
        f.write(data)
    logger.info(f"Saved '{safe_name}' to local {local_folder}/")


def delete_document(filename: str, local_folder: str = "documents") -> None:
    """Delete a document from Azure Blob Storage and local folder."""
    safe_name = os.path.basename(filename)
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "documents")

    if connection_string:
        try:
            from azure.storage.blob import BlobServiceClient
            client = BlobServiceClient.from_connection_string(connection_string)
            client.get_blob_client(container=container_name, blob=safe_name).delete_blob()
            logger.info(f"Deleted '{safe_name}' from Azure Blob Storage")
        except Exception as e:
            logger.warning(f"Azure delete failed: {e}")

    local_path = os.path.join(local_folder, safe_name)
    if os.path.exists(local_path):
        os.remove(local_path)
        logger.info(f"Deleted '{safe_name}' from local {local_folder}/")
