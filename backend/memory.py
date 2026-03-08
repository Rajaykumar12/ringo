"""
memory.py — Conversation session memory.
Uses Redis (with 1-hour TTL) when available; falls back to in-memory store.
"""
import os
from typing import Dict
from langchain_core.chat_history import InMemoryChatMessageHistory

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")

# In-memory fallback store (used when Redis is unavailable)
_memory_store: Dict[str, InMemoryChatMessageHistory] = {}


def get_session_history(session_id: str):
    """Return conversation history for a session.
    Uses Redis if available (TTL: 1 hour), in-memory otherwise.
    """
    try:
        from langchain_community.chat_message_histories import RedisChatMessageHistory
        history = RedisChatMessageHistory(session_id=session_id, url=REDIS_URL, ttl=3600)
        # Probe connection — raises if Redis is down
        _ = history.messages
        return history
    except Exception:
        if session_id not in _memory_store:
            _memory_store[session_id] = InMemoryChatMessageHistory()
        return _memory_store[session_id]
