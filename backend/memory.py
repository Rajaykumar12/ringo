"""
memory.py — Conversation session memory.
Uses Redis (with 1-hour TTL) when available; falls back to in-memory LRU store.
Both are write-through to conversation_store.py's SQLite table, so a conversation
survives a Redis eviction or a backend restart — see _PersistentHistory below.
"""
import logging
import os
from collections import OrderedDict
from typing import List, Optional, Sequence
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

import conversation_store

logger = logging.getLogger("ringo.memory")

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
        logger.info("Redis connected at %s", REDIS_URL)
    except Exception as e:
        _redis_ok = False
        logger.warning("Redis unavailable (%s) — using in-memory session store", e)
    return _redis_ok


class _PersistentHistory(BaseChatMessageHistory):
    """Wraps a hot-path history (Redis or in-memory) with a SQLite write-through.

    Every add_messages call is persisted to conversation_store.py *and* forwarded
    to the backing store, so the backing store stays the fast path for reads while
    SQLite is the durable copy. If the backing store comes up empty (a fresh Redis
    TTL expiry, an evicted in-memory LRU slot, or a fresh process after a restart),
    the last SESSION_MAX_MESSAGES turns are replayed in from SQLite once, on first
    access, so a reload/restart doesn't silently start the conversation over.
    """

    def __init__(self, session_id: str, backing):
        self.session_id = session_id
        self._backing = backing
        self._hydrated = False

    def _hydrate_if_empty(self) -> None:
        if self._hydrated:
            return
        self._hydrated = True
        if self._backing.messages:
            return  # backing store already has history — nothing to recover
        rows = conversation_store.get_messages(self.session_id)
        if not rows:
            return
        recent = rows[-SESSION_MAX_MESSAGES:]
        replayed: List[BaseMessage] = [
            (HumanMessage if row["role"] == "human" else AIMessage)(content=row["content"])
            for row in recent
        ]
        self._backing.add_messages(replayed)
        logger.info("Hydrated %d messages for session %s from SQLite", len(replayed), self.session_id)

    @property
    def messages(self) -> List[BaseMessage]:
        self._hydrate_if_empty()
        return self._backing.messages

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        self._hydrate_if_empty()
        self._backing.add_messages(list(messages))
        for m in messages:
            role = "human" if isinstance(m, HumanMessage) else "ai"
            try:
                conversation_store.append_message(self.session_id, role, m.content)
            except Exception as e:
                logger.warning("Failed to persist message for session %s: %s", self.session_id, e)

    def clear(self) -> None:
        self._backing.clear()
        try:
            conversation_store.clear_session(self.session_id)
        except Exception as e:
            logger.warning("Failed to clear persisted history for session %s: %s", self.session_id, e)


def get_session_history(session_id: str) -> _PersistentHistory:
    """Return conversation history for a session.
    Uses Redis if available (TTL: 1 hour), in-memory LRU otherwise, wrapped so every
    write also lands in SQLite (conversation_store.py) for durability across
    Redis evictions and backend restarts.
    """
    if _probe_redis():
        from langchain_community.chat_message_histories import RedisChatMessageHistory
        backing = RedisChatMessageHistory(session_id=session_id, url=REDIS_URL, ttl=3600)
        return _PersistentHistory(session_id, backing)

    # In-memory LRU path
    if session_id in _memory_store:
        _memory_store.move_to_end(session_id)
    else:
        if len(_memory_store) >= MAX_SESSIONS:
            _memory_store.popitem(last=False)  # evict oldest
        _memory_store[session_id] = InMemoryChatMessageHistory()

    backing = _memory_store[session_id]

    # Trim to avoid unbounded context growth
    msgs = backing.messages
    if len(msgs) > SESSION_MAX_MESSAGES:
        trimmed = msgs[-SESSION_MAX_MESSAGES:]
        backing.clear()
        backing.add_messages(trimmed)

    return _PersistentHistory(session_id, backing)
