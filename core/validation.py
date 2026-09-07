"""
Shared transcript input validation (Phase 1, C5). One function, applied
uniformly to every entry path that accepts or produces a pitch
transcript:
  - typed text — models.schemas.FilterRequest.transcript,
    routers.phase3.AnalyzeRequest.transcript (both via a Pydantic
    field_validator, so a violation surfaces as FastAPI's standard
    structured 422 body — a list of {type, loc, msg} entries naming the
    field and violation).
  - audio — routers/phase1.py's /transcribe calls this manually on
    Whisper's output before returning it, raising the same
    TranscriptValidationError, translated to an explicit structured 422
    body there since there's no request-body Pydantic model to validate
    (the transcript doesn't exist until after the Groq call runs).
  - video — no video-transcript endpoint exists in this codebase yet;
    when one is added, route its transcription output through this same
    function rather than duplicating checks, exactly like /transcribe.
"""
import unicodedata

from core.config import TRANSCRIPT_MAX_LENGTH

# Control characters (Unicode category Cc) are stripped except the three
# whitespace ones that carry real structure in a pitch transcript — a
# blank line or an indented list item is still meaningful text, not junk.
_KEEP_CONTROL_CHARS = {"\n", "\r", "\t"}


class TranscriptValidationError(ValueError):
    """violation is a short machine-readable tag (empty | too_long) for
    callers that want to branch on it; str(self) / args[0] is the
    human-readable detail returned to the client."""

    def __init__(self, violation: str, detail: str):
        self.violation = violation
        self.detail = detail
        super().__init__(detail)


def strip_control_characters(text: str) -> str:
    return "".join(
        ch for ch in text
        if ch in _KEEP_CONTROL_CHARS or unicodedata.category(ch) != "Cc"
    )


def validate_transcript(raw: str | None, *, max_length: int = TRANSCRIPT_MAX_LENGTH) -> str:
    """Returns the sanitized transcript (control characters stripped,
    surrounding whitespace trimmed) or raises TranscriptValidationError
    naming the specific violation. Emptiness is checked AFTER sanitizing,
    so a submission that's nothing but control characters or whitespace
    is correctly caught as empty rather than accepted as "content"."""
    if raw is None:
        raise TranscriptValidationError("empty", "Transcript is required.")

    sanitized = strip_control_characters(raw).strip()

    if not sanitized:
        raise TranscriptValidationError("empty", "Transcript is empty or whitespace-only.")

    if len(sanitized) > max_length:
        raise TranscriptValidationError(
            "too_long",
            f"Transcript exceeds the maximum length of {max_length} characters (got {len(sanitized)}).",
        )

    return sanitized
