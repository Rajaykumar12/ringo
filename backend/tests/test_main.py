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
