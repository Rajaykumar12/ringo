import asyncio
import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

import main


def test_validate_session_id_rejects_too_long():
    with pytest.raises(HTTPException) as exc_info:
        main._validate_session_id("x" * 129)
    assert exc_info.value.status_code == 400


def test_validate_session_id_accepts_minted_token():
    main._validate_session_id(f"session_{uuid.uuid4()}")  # should not raise


@pytest.mark.parametrize(
    "bad",
    [
        "default",              # the old shared sentinel — must never be accepted
        "normal_session_id",    # arbitrary caller-chosen string
        "session_not-a-uuid",
        "session_",
        "",
        f"session_{uuid.uuid4()}x",
    ],
)
def test_validate_session_id_rejects_guessable_values(bad):
    """session_id is the bearer capability for GET /conversations, so anything a
    caller could guess or collide on has to be refused."""
    with pytest.raises(HTTPException) as exc_info:
        main._validate_session_id(bad)
    assert exc_info.value.status_code == 400


def test_log_id_regex_accepts_uuid_like_string():
    assert main._LOG_ID_RE.match("abc-123_XYZ") is not None


def test_log_id_regex_rejects_special_characters():
    assert main._LOG_ID_RE.match("bad id!") is None


def test_log_date_regex_accepts_iso_date():
    assert main._LOG_DATE_RE.match("2026-07-13") is not None


def test_log_date_regex_rejects_non_iso_date():
    assert main._LOG_DATE_RE.match("13-07-2026") is None


def test_health_live_reports_alive():
    result = asyncio.run(main.health_live())
    assert result == {"status": "alive"}


def test_health_reports_degraded_status_when_dependencies_unavailable():
    # Groq check is mocked so this test doesn't depend on network/real credentials.
    # rag_system is not initialized (no lifespan run) and Redis is not necessarily
    # running in CI, so both should gracefully report their fallback status.
    with patch("main._check_groq_reachable", return_value=False):
        result = asyncio.run(main.health())
    assert result["status"] == "healthy"
    assert result["vector_store"] == "uninitialized"
    assert result["groq"] == "unreachable"
    assert result["redis"] in ("connected", "unavailable (using in-memory fallback)")


# ── Rate-limit keying behind a reverse proxy (SEC-4) ──────────────────────────

class _FakeClient:
    def __init__(self, host): self.host = host


class _FakeRequest:
    def __init__(self, peer, method="POST", forwarded=None):
        self.method = method
        self.client = _FakeClient(peer)
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


def test_rate_limit_key_uses_peer_when_no_proxy_configured(monkeypatch):
    """Default posture: no proxy is trusted, so a spoofed header is ignored."""
    monkeypatch.setattr(main, "TRUSTED_PROXY_IPS", set())
    req = _FakeRequest("203.0.113.9", forwarded="1.2.3.4")
    assert main._rate_limit_key(req) == "203.0.113.9"


def test_rate_limit_key_honours_forwarded_from_trusted_proxy(monkeypatch):
    """Behind the configured proxy every request shares one peer address, so the
    originating client must come from X-Forwarded-For or nobody is limited."""
    monkeypatch.setattr(main, "TRUSTED_PROXY_IPS", {"172.18.0.3"})
    req = _FakeRequest("172.18.0.3", forwarded="203.0.113.7, 172.18.0.3")
    assert main._rate_limit_key(req) == "203.0.113.7"  # left-most = originating client


def test_rate_limit_key_ignores_forwarded_from_untrusted_peer(monkeypatch):
    """A direct caller must not be able to mint its own bucket by sending the header."""
    monkeypatch.setattr(main, "TRUSTED_PROXY_IPS", {"172.18.0.3"})
    req = _FakeRequest("203.0.113.9", forwarded="10.0.0.1")
    assert main._rate_limit_key(req) == "203.0.113.9"


def test_rate_limit_key_distinguishes_clients_behind_one_proxy(monkeypatch):
    monkeypatch.setattr(main, "TRUSTED_PROXY_IPS", {"172.18.0.3"})
    a = main._rate_limit_key(_FakeRequest("172.18.0.3", forwarded="203.0.113.1"))
    b = main._rate_limit_key(_FakeRequest("172.18.0.3", forwarded="203.0.113.2"))
    assert a != b


def test_rate_limit_key_exempts_cors_preflight():
    assert main._rate_limit_key(_FakeRequest("203.0.113.9", method="OPTIONS")) is None
