import pytest
from fastapi.testclient import TestClient
from main import app
from services.keyword_extractor import extract_keyword, KeywordExtractionError
from core.config import FILTER_MODEL


async def test_extract_keyword_success(monkeypatch):
    async def _fake_chat(model, system, user, max_tokens):
        assert model == FILTER_MODEL
        return "AI code review"

    monkeypatch.setattr("services.keyword_extractor.chat", _fake_chat)
    keyword = await extract_keyword("We build automated code reviews for enterprises.")
    assert keyword == "AI code review"


async def test_extract_keyword_too_short(monkeypatch):
    async def _fake_chat(model, system, user, max_tokens):
        return "a"

    monkeypatch.setattr("services.keyword_extractor.chat", _fake_chat)
    with pytest.raises(KeywordExtractionError):
        await extract_keyword("Some pitch transcript")


async def test_extract_keyword_too_long(monkeypatch):
    async def _fake_chat(model, system, user, max_tokens):
        return "one two three four five six seven eight nine ten words"

    monkeypatch.setattr("services.keyword_extractor.chat", _fake_chat)
    with pytest.raises(KeywordExtractionError):
        await extract_keyword("Some pitch transcript")


def test_analyze_uses_manual_keyword_override(monkeypatch):
    client = TestClient(app)
    extracted_called = False

    async def _fake_extract(transcript):
        nonlocal extracted_called
        extracted_called = True
        return "extracted topic"

    monkeypatch.setattr("routers.phase3.extract_keyword", _fake_extract)

    # Stream analysis mocked or bypassed
    async def _fake_stream(transcript, keyword, signals, session_id=None, ip=None, filter_result=None):
        yield f"data: {keyword}\n\n"

    monkeypatch.setattr("routers.phase3.stream_analysis", _fake_stream)

    res = client.post(
        "/api/phase3/analyze",
        json={"transcript": "test pitch", "keyword": "manual topic", "signals": {}},
        headers={"X-Session-Id": "test-session-123"},
    )
    assert res.status_code == 200
    assert not extracted_called
    assert "manual topic" in res.text


def test_analyze_extracts_keyword_when_omitted(monkeypatch):
    client = TestClient(app)

    async def _fake_extract(transcript):
        return "auto extracted topic"

    monkeypatch.setattr("routers.phase3.extract_keyword", _fake_extract)

    async def _fake_stream(transcript, keyword, signals, session_id=None, ip=None, filter_result=None):
        yield f"data: {keyword}\n\n"

    monkeypatch.setattr("routers.phase3.stream_analysis", _fake_stream)

    res = client.post(
        "/api/phase3/analyze",
        json={"transcript": "test pitch", "signals": {}},
        headers={"X-Session-Id": "test-session-456"},
    )
    assert res.status_code == 200
    assert "auto extracted topic" in res.text


def test_analyze_rejects_on_extraction_error_422(monkeypatch):
    client = TestClient(app)

    async def _fake_extract(transcript):
        raise KeywordExtractionError("Failed")

    monkeypatch.setattr("routers.phase3.extract_keyword", _fake_extract)

    res = client.post(
        "/api/phase3/analyze",
        json={"transcript": "gibberish", "signals": {}},
        headers={"X-Session-Id": "test-session-789"},
    )
    assert res.status_code == 422
    assert res.json()["detail"] == "couldn't extract a clear topic from this pitch — try being more specific"
