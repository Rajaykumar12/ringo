"""
image_store.py — Local filesystem storage for images extracted from RAG documents
and uploaded by users in chat. Sibling of document_store.py; follows the same
local-folder convention as backend/documents/ and backend/data/rag_logs.db.
"""
import logging
import os
import uuid
from typing import Optional, Tuple

logger = logging.getLogger("ringo.image_store")

IMAGES_DIR = os.environ.get(
    "IMAGES_DIR", os.path.join(os.path.dirname(__file__), "data", "images")
)

_EXT_BY_MIME = {
    "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
    "image/webp": ".webp", "image/gif": ".gif", "image/bmp": ".bmp",
}

_MIME_BY_EXT = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "gif": "image/gif", "bmp": "image/bmp",
}


def _ext_for(mime_type: Optional[str]) -> str:
    if not mime_type:
        return ".png"
    if mime_type in _EXT_BY_MIME:
        return _EXT_BY_MIME[mime_type]
    # PyMuPDF/python-pptx sometimes give raw formats like "png"/"jpeg" instead of a MIME type
    bare = mime_type.lstrip(".").lower()
    if bare in _MIME_BY_EXT:
        return f".{bare}"
    return ".png"


def save_image(data: bytes, mime_type: Optional[str] = None) -> str:
    """Persist raw image bytes under a new uuid4-based id. Returns the image_id
    (bare hex uuid, no extension — extension is resolved on load)."""
    os.makedirs(IMAGES_DIR, exist_ok=True)
    image_id = uuid.uuid4().hex
    ext = _ext_for(mime_type)
    path = os.path.join(IMAGES_DIR, f"{image_id}{ext}")
    with open(path, "wb") as f:
        f.write(data)
    logger.debug("Saved image %s (%d bytes)", image_id, len(data))
    return image_id


def _resolve_path(image_id: str) -> Optional[str]:
    """Validate image_id is a bare hex uuid (no path separators) and locate its file
    on disk regardless of extension. Returns None if invalid or missing — callers
    MUST treat None as not-found, never fall back to raw path construction (traversal guard)."""
    if not image_id or len(image_id) != 32 or not all(c in "0123456789abcdef" for c in image_id):
        return None
    if not os.path.isdir(IMAGES_DIR):
        return None
    for fname in os.listdir(IMAGES_DIR):
        stem, _ = os.path.splitext(fname)
        if stem == image_id:
            return os.path.join(IMAGES_DIR, fname)
    return None


def load_image(image_id: str) -> Optional[Tuple[bytes, str]]:
    """Returns (bytes, mime_type) or None if not found."""
    path = _resolve_path(image_id)
    if not path:
        return None
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    mime = _MIME_BY_EXT.get(ext, "application/octet-stream")
    with open(path, "rb") as f:
        return f.read(), mime


def delete_image(image_id: str) -> bool:
    path = _resolve_path(image_id)
    if not path:
        return False
    try:
        os.remove(path)
        return True
    except OSError as e:
        logger.warning("Failed to delete image %s: %s", image_id, e)
        return False
