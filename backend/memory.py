"""
memory.py — Conversation session memory.
Uses Redis (with 1-hour TTL) when available; falls back to in-memory LRU store.
"""
import os
from collections import OrderedDict
from typing import Optional
from langchain_core.chat_history import InMemoryChatMessageHistory

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

MAX_SESSIONS = 500        # Max in-memory sessions before evicting oldest
SESSION_MAX_MESSAGES = 50 # Max messages kept per session to bound context size

# In-memory LRU fallback store (used when Redis is unavailable)
_memory_store: OrderedDict = OrderedDict()
_redis_ok: Optional[bool] = None  # None = not yet probed


def _probe_redis() -> bool:
    """Check Redis connectivity once at first call; cache the result."""
    global _redis_ok
    if _redis_ok is not None:
        return _redis_ok
    try:
        from langchain_community.chat_message_histories import RedisChatMessageHistory
        h = RedisChatMessageHistory(session_id="__probe__", url=REDIS_URL)
        _ = h.messages
        _redis_ok = True
        print(f"Redis connected at {REDIS_URL}")
    except Exception as e:
        _redis_ok = False
        print(f"Redis unavailable ({e}) — using in-memory session store")
    return _redis_ok


def get_session_history(session_id: str):
    """Return conversation history for a session.
    Uses Redis if available (TTL: 1 hour), in-memory LRU otherwise.
    """
    if _probe_redis():
        from langchain_community.chat_message_histories import RedisChatMessageHistory
        return RedisChatMessageHistory(session_id=session_id, url=REDIS_URL, ttl=3600)

    # In-memory LRU path
    if session_id in _memory_store:
        _memory_store.move_to_end(session_id)
    else:
        if len(_memory_store) >= MAX_SESSIONS:
            _memory_store.popitem(last=False)  # evict oldest
        _memory_store[session_id] = InMemoryChatMessageHistory()

    history = _memory_store[session_id]

    # Trim to avoid unbounded context growth
    msgs = history.messages
    if len(msgs) > SESSION_MAX_MESSAGES:
        trimmed = msgs[-SESSION_MAX_MESSAGES:]
        history.clear()
        history.add_messages(trimmed)

    return history
