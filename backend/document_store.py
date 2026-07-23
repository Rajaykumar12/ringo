"""
document_store.py — Local filesystem document storage.
Documents live in `documents_folder` (default 'documents'), typically mounted as a
Docker volume so uploads survive container restarts.
"""
import logging
import os

logger = logging.getLogger("ringo.document_store")

ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".md", ".docx", ".html", ".csv", ".xlsx"}
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 20 * 1024 * 1024))  # 20 MB default


def ensure_documents_folder(local_folder: str = "documents") -> None:
    """Make sure the documents folder exists before the vectorstore scans it."""
    os.makedirs(local_folder, exist_ok=True)


def upload_document(filename: str, data: bytes, local_folder: str = "documents") -> None:
    """Save an uploaded document to the local documents folder."""
    # Sanitize filename — strip any path components
    safe_name = os.path.basename(filename)
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File too large ({len(data)} bytes). Maximum is {MAX_UPLOAD_BYTES // (1024*1024)} MB.")

    os.makedirs(local_folder, exist_ok=True)
    with open(os.path.join(local_folder, safe_name), "wb") as f:
        f.write(data)
    logger.info(f"Saved '{safe_name}' to {local_folder}/")


def delete_document(filename: str, local_folder: str = "documents") -> None:
    """Delete a document from the local documents folder."""
    safe_name = os.path.basename(filename)
    local_path = os.path.join(local_folder, safe_name)
    if os.path.exists(local_path):
        os.remove(local_path)
        logger.info(f"Deleted '{safe_name}' from {local_folder}/")
