"""C5 — transcript input validation: length cap, control-character
stripping, empty/whitespace-only rejection, structured 422s across every
entry path (typed text, audio)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.validation import TranscriptValidationError, validate_transcript
from models.schemas import FilterRequest
from routers import phase1
from routers.phase3 import AnalyzeRequest


# ── core.validation.validate_transcript ─────────────────────

def test_valid_transcript_passes_through_unchanged():
    assert validate_transcript("A clear pitch about dog walking.") == "A clear pitch about dog walking."


def test_none_is_rejected_as_empty():
    with pytest.raises(TranscriptValidationError) as exc:
        validate_transcript(None)
    assert exc.value.violation == "empty"


def test_empty_string_rejected():
    with pytest.raises(TranscriptValidationError) as exc:
        validate_transcript("")
    assert exc.value.violation == "empty"


def test_whitespace_only_rejected():
    with pytest.raises(TranscriptValidationError) as exc:
        validate_transcript("   \n\t  ")
    assert exc.value.violation == "empty"


def test_control_characters_only_rejected_as_empty():
    """A string that's pure control-character noise (e.g. NUL bytes) has
    no real content once sanitized, and must be treated as empty — not
    accepted just because len(raw) > 0."""
    with pytest.raises(TranscriptValidationError) as exc:
        validate_transcript("\x00\x01\x02\x03")
    assert exc.value.violation == "empty"


def test_control_characters_stripped_from_otherwise_valid_text():
    result = validate_transcript("We help\x00 freelancers\x07 invoice clients.")
    assert "\x00" not in result
    assert "\x07" not in result
    assert "We help" in result and "invoice clients" in result


def test_newlines_tabs_and_carriage_returns_preserved():
    result = validate_transcript("Line one.\nLine two.\tTabbed.\r\n")
    assert "\n" in result
    assert "\t" in result


def test_leading_trailing_whitespace_trimmed():
    assert validate_transcript("   hello world   ") == "hello world"


def test_exactly_at_max_length_is_allowed():
    text = "a" * 5000
    assert validate_transcript(text, max_length=5000) == text


def test_over_max_length_rejected():
    text = "a" * 5001
    with pytest.raises(TranscriptValidationError) as exc:
        validate_transcript(text, max_length=5000)
    assert exc.value.violation == "too_long"
    assert "5000" in exc.value.detail


def test_max_length_is_configurable_per_call():
    with pytest.raises(TranscriptValidationError):
        validate_transcript("a" * 11, max_length=10)
    assert validate_transcript("a" * 10, max_length=10) == "a" * 10


def test_default_max_length_matches_config():
    from core.config import TRANSCRIPT_MAX_LENGTH
    assert TRANSCRIPT_MAX_LENGTH == 5000
    with pytest.raises(TranscriptValidationError):
        validate_transcript("a" * (TRANSCRIPT_MAX_LENGTH + 1))


# ── Pydantic model validators (FilterRequest / AnalyzeRequest) ──

def test_filter_request_rejects_empty_transcript():
    with pytest.raises(ValidationError):
        FilterRequest(transcript="")


def test_filter_request_rejects_too_long_transcript():
    with pytest.raises(ValidationError):
        FilterRequest(transcript="a" * 5001)


def test_filter_request_accepts_and_sanitizes_valid_transcript():
    req = FilterRequest(transcript="  We help plumbers invoice faster.  ")
    assert req.transcript == "We help plumbers invoice faster."


def test_analyze_request_rejects_empty_transcript():
    with pytest.raises(ValidationError):
        AnalyzeRequest(transcript="   ", signals={})


def test_analyze_request_rejects_too_long_transcript():
    with pytest.raises(ValidationError):
        AnalyzeRequest(transcript="a" * 5001, signals={})


def test_analyze_request_accepts_valid_transcript():
    req = AnalyzeRequest(transcript="Uber for dog walking", signals={})
    assert req.transcript == "Uber for dog walking"


# ── Router-level: structured 422s ───────────────────────────

filter_app = FastAPI()
filter_app.include_router(phase1.router, prefix="/api/phase1")
filter_client = TestClient(filter_app)


def test_filter_endpoint_422_on_empty_transcript():
    res = filter_client.post("/api/phase1/filter", json={"transcript": "   "})
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert isinstance(detail, list)
    assert any("empty" in str(err.get("msg", "")).lower() for err in detail)


def test_filter_endpoint_422_on_too_long_transcript():
    res = filter_client.post("/api/phase1/filter", json={"transcript": "a" * 5001})
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert any("5000" in str(err.get("msg", "")) for err in detail)


def test_transcribe_endpoint_422_on_too_long_result(monkeypatch):
    async def _fake_transcribe(audio_bytes, filename="pitch.webm", **kwargs):
        return "a" * 5001

    monkeypatch.setattr(phase1, "transcribe_audio", _fake_transcribe)

    res = filter_client.post(
        "/api/phase1/transcribe",
        files={"audio": ("pitch.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["violation"] == "too_long"


def test_transcribe_endpoint_strips_control_characters(monkeypatch):
    async def _fake_transcribe(audio_bytes, filename="pitch.webm", **kwargs):
        return "We help\x00 plumbers invoice\x07 faster."

    monkeypatch.setattr(phase1, "transcribe_audio", _fake_transcribe)

    res = filter_client.post(
        "/api/phase1/transcribe",
        files={"audio": ("pitch.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert res.status_code == 200
    transcript = res.json()["transcript"]
    assert "\x00" not in transcript
    assert "\x07" not in transcript
