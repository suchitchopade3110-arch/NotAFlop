"""
Shared unavailability-signal envelope (Phase 1, B2) every data source's
output gets normalized into before it reaches agents, signal_quality, or
conflict detection.

Additive by design: services/data_sources/*.py adapters keep their
existing fetch() signature and internals untouched (per Phase 1 hard
constraint #1) — normalization happens in one place, centrally, in
services.smart_data_layer, which wraps each adapter's raw output rather
than the adapters rewriting themselves to produce it directly.

Every source ends up in exactly one of five states:
  - ok:            live call succeeded, payload has real records.
  - empty:         live call succeeded, source confirmed there's nothing
                    (e.g. hit_count == 0) — "no signal found", not a failure.
  - rate_limited:   live call was made but rejected (HTTP 429 or similar).
  - unavailable:    never attempted — not configured, or no live
                    implementation exists yet (e.g. wellfound today).
  - error:          live call was attempted and failed for some other
                    reason (timeout, 5xx, malformed response, ...).

Agents must be able to tell "checked, found nothing" (empty) apart from
"could not check" (rate_limited / unavailable / error) — see the module
docstring on services/signal_quality.py for how that distinction is used.
"""
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class SignalStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


class SignalResult(BaseModel):
    """Canonical per-source result shape. `payload` carries the source's
    own domain fields verbatim (post_count, hit_count, trend, ...) — this
    envelope only adds a uniform status/timestamp/reason around them, it
    never reshapes or drops them."""

    source: str
    status: SignalStatus
    payload: dict | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str | None = None


# Per-source hint for whether a successful fetch actually found anything —
# purely used to tell "ok" apart from "empty" below. Not exhaustive of every
# field a source returns; only the ones that indicate record count.
_EMPTY_CHECKS = {
    "google_trends": lambda p: not p.get("raw"),
    "hacker_news": lambda p: not p.get("hit_count") and not p.get("sample_posts"),
    "product_hunt": lambda p: not p.get("launch_count") and not p.get("top_products"),
    "reddit": lambda p: not p.get("post_count") and not p.get("sample_posts"),
    "wellfound": lambda p: not p.get("startup_count") and not p.get("top_startups"),
}

_RATE_LIMIT_MARKERS = ("429", "rate limit", "too many requests")
_STRUCTURAL_UNAVAILABLE_MARKERS = ("not configured", "not yet implemented")


def _is_empty(source: str, payload: dict) -> bool:
    check = _EMPTY_CHECKS.get(source)
    return bool(check(payload)) if check else False


def normalize_source_result(source: str, raw: dict | BaseException) -> SignalResult:
    """Wraps one adapter's raw fetch() output (or the exception asyncio.gather
    caught in its place) into a SignalResult. Never invents payload data —
    every non-ok/empty branch carries payload=None."""
    if isinstance(raw, BaseException):
        return SignalResult(source=source, status=SignalStatus.ERROR, reason=f"live fetch failed: {raw}")

    if not isinstance(raw, dict):
        return SignalResult(
            source=source, status=SignalStatus.ERROR,
            reason=f"unexpected adapter output type: {type(raw).__name__}",
        )

    status_field = raw.get("status")

    if status_field in ("unavailable", "rate_limited", "error"):
        reason = str(raw.get("reason", ""))
        lowered = reason.lower()
        if status_field == "rate_limited" or any(m in lowered for m in _RATE_LIMIT_MARKERS):
            return SignalResult(source=source, status=SignalStatus.RATE_LIMITED, reason=reason)
        if status_field == "unavailable" and any(m in lowered for m in _STRUCTURAL_UNAVAILABLE_MARKERS):
            return SignalResult(source=source, status=SignalStatus.UNAVAILABLE, reason=reason)
        # A live attempt was made (or explicitly marked as one) and failed
        # for some other reason — timeout, 5xx, parse error, etc.
        return SignalResult(source=source, status=SignalStatus.ERROR, reason=reason)

    # No status field at all -> today's adapters only omit it on a genuine
    # successful fetch.
    payload = {k: v for k, v in raw.items() if k not in {"status", "reason"}}
    if _is_empty(source, payload):
        return SignalResult(source=source, status=SignalStatus.EMPTY, payload=payload)
    return SignalResult(source=source, status=SignalStatus.OK, payload=payload)


def coerce_to_signal_result(source: str, raw) -> SignalResult:
    """Accepts either an already-normalized SignalResult-shaped dict (what
    smart_data_layer.gather_signals now produces) or a legacy flat
    per-source dict (what existing callers/tests still pass straight into
    /analyze, predating B2) and returns a SignalResult either way. Used by
    signal_quality and conflict_detector so both work regardless of which
    shape actually reached the orchestrator."""
    if (
        isinstance(raw, dict)
        and "status" in raw and "payload" in raw and "fetched_at" in raw
    ):
        try:
            return SignalResult.model_validate(raw)
        except Exception:
            pass
    return normalize_source_result(source, raw)
