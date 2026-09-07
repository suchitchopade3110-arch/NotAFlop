"""C2 — structured logging: request_id propagation, session_id binding,
and the pitch-text-at-info-level PII guard."""
import logging

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.middleware import REQUEST_ID_HEADER, RequestIDMiddleware
from core.session import SESSION_HEADER, get_session_context
from services import keyword_extractor
from services.keyword_extractor import extract_keyword


# ── RequestIDMiddleware ──────────────────────────────────────

app = FastAPI()
app.add_middleware(RequestIDMiddleware)


@app.get("/ping")
async def ping():
    return {"ok": True}


client = TestClient(app)


def test_response_carries_a_request_id_header():
    res = client.get("/ping")
    assert res.status_code == 200
    assert res.headers.get(REQUEST_ID_HEADER)


def test_inbound_request_id_is_echoed_back():
    res = client.get("/ping", headers={REQUEST_ID_HEADER: "caller-supplied-id"})
    assert res.headers[REQUEST_ID_HEADER] == "caller-supplied-id"


def test_each_request_gets_a_fresh_request_id_by_default():
    r1 = client.get("/ping")
    r2 = client.get("/ping")
    assert r1.headers[REQUEST_ID_HEADER] != r2.headers[REQUEST_ID_HEADER]


# ── session_id binding (core/session.py) ────────────────────

async def test_get_session_context_binds_session_id_into_log_context(mongo_db):
    from starlette.requests import Request
    from starlette.responses import Response

    scope = {
        "type": "http", "method": "GET", "path": "/x", "headers": [],
        "client": ("1.2.3.4", 1234), "query_string": b"",
    }
    request = Request(scope)
    response = Response()

    structlog.contextvars.clear_contextvars()
    ctx = await get_session_context(request, response)
    bound = structlog.contextvars.get_contextvars()
    assert bound.get("session_id") == ctx.session_id
    structlog.contextvars.clear_contextvars()


# ── PII guard: pitch text never logged, not even truncated ─────

async def test_extracted_keyword_log_never_contains_transcript_text(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="notaflop.keyword_extractor")

    async def _fake_chat(model, system, user, max_tokens, **kwargs):
        return "AI code review"

    monkeypatch.setattr(keyword_extractor, "chat", _fake_chat)

    secret_pitch = "We help SECRET_STARTUP_NAME automate proprietary invoicing workflows for enterprises."
    keyword = await extract_keyword(secret_pitch)

    assert keyword == "AI code review"
    assert "extracted_keyword" in caplog.text
    assert "keyword=AI code review" in caplog.text
    # the actual guard: no substring of the pitch text ever reaches the log
    assert "SECRET_STARTUP_NAME" not in caplog.text
    assert secret_pitch not in caplog.text
    # length is fine to log — content is not
    assert f"transcript_len={len(secret_pitch)}" in caplog.text


async def test_rejected_keyword_log_never_contains_transcript_text(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger="notaflop.keyword_extractor")

    async def _fake_chat(model, system, user, max_tokens, **kwargs):
        return "a"  # too short -> rejected path

    monkeypatch.setattr(keyword_extractor, "chat", _fake_chat)

    secret_pitch = "CONFIDENTIAL_DEAL_TERMS pitch transcript that must never be logged verbatim."
    with pytest.raises(keyword_extractor.KeywordExtractionError):
        await extract_keyword(secret_pitch)

    assert "extracted_keyword_rejected" in caplog.text
    assert "CONFIDENTIAL_DEAL_TERMS" not in caplog.text
    assert secret_pitch not in caplog.text
