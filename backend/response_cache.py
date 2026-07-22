"""
response_cache.py — Exact-match cache for first-turn RAG responses.
Uses Redis (with TTL) when available; falls back to an in-memory LRU store.
Only meant to be consulted for first-turn queries (empty conversation history) —
a cached answer doesn't account for a session's prior context, so callers must
gate its use on that themselves.
"""
import hashlib
import logging
import os
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger("ringo.response_cache")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
RESPONSE_CACHE_TTL_SECONDS = int(os.environ.get("RESPONSE_CACHE_TTL_SECONDS", "3600"))
MAX_MEMORY_CACHE_ENTRIES = 500

_memory_cache: "OrderedDict[str, str]" = OrderedDict()
_redis_client = None
_redis_ok: Optional[bool] = None


def _get_redis():
    global _redis_client, _redis_ok
    if _redis_ok is not None:
        return _redis_client if _redis_ok else None
    try:
        import redis
        client = redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        _redis_client = client
        _redis_ok = True
        logger.info("Response cache using Redis at %s", REDIS_URL)
    except Exception as e:
        _redis_ok = False
        logger.warning("Redis unavailable for response cache (%s) — using in-memory cache", e)
    return _redis_client if _redis_ok else None


def make_cache_key(query: str, context: str) -> str:
    normalized = query.strip().lower()
    digest = hashlib.sha256(f"{normalized}|{context}".encode("utf-8")).hexdigest()
    return f"ringo:response_cache:{digest}"


def get_cached_response(key: str) -> Optional[str]:
    client = _get_redis()
    if client is not None:
        try:
            value = client.get(key)
            return value.decode("utf-8") if value else None
        except Exception as e:
            logger.warning("Response cache read failed: %s", e)
            return None
    if key in _memory_cache:
        _memory_cache.move_to_end(key)
        return _memory_cache[key]
    return None


def set_cached_response(key: str, response: str):
    client = _get_redis()
    if client is not None:
        try:
            client.setex(key, RESPONSE_CACHE_TTL_SECONDS, response)
        except Exception as e:
            logger.warning("Response cache write failed: %s", e)
        return
    if key in _memory_cache:
        _memory_cache.move_to_end(key)
    elif len(_memory_cache) >= MAX_MEMORY_CACHE_ENTRIES:
        _memory_cache.popitem(last=False)
    _memory_cache[key] = response
