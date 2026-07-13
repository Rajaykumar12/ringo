import asyncio
from unittest.mock import patch

import pytest
from fastapi import HTTPException

import main


def test_validate_session_id_rejects_too_long():
    with pytest.raises(HTTPException) as exc_info:
        main._validate_session_id("x" * 129)
    assert exc_info.value.status_code == 400


def test_validate_session_id_accepts_normal_length():
    main._validate_session_id("normal_session_id")  # should not raise


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
