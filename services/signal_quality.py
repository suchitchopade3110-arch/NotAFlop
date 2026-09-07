"""
Signal quality (Phase 1, B3) — a disclosure layer on top of the
SignalResult envelope (services.data_sources.result), telling a reader
how much live evidence actually backed a report.

Purely observational: nothing here feeds back into aggregate_results(),
WEIGHTS, or the gate (services/gate.py) — see Phase 1 hard constraints
#6/#7. A low signal_quality changes what's disclosed about a verdict, not
the verdict's score.

Rule-based, no LLM call. Quality is computed from three inputs per
source, each honestly derived from the SignalResult itself:
  - status: 0 for anything that isn't ok/empty (no live data was
    obtained, full stop); a partial credit for empty (the source WAS
    reached — that's still meaningful signal of absence — deliberately
    less than a real result).
  - record count: more corroborating records -> more confidence, capped
    so one source can't dominate.
  - freshness: a cache hit still counts as live-sourced data (same
    24h TTL window), just a small discount vs an in-this-request fetch.
"""
from services.data_sources.result import SignalResult, SignalStatus, coerce_to_signal_result

# live_data (status == OK) minimum source count below which a report is
# flagged low_confidence — see compute_report_signal_quality.
MIN_LIVE_SOURCES = 2

_EMPTY_QUALITY = 0.3
_OK_BASE_QUALITY = 0.7
_RECORD_COUNT_BONUS_CAP = 0.3
_RECORD_COUNT_FOR_FULL_BONUS = 100
_CACHED_DISCOUNT = 0.95

# Field on each source's payload that best approximates "how many records
# backed this result" — used only for the record-count bonus, never to
# decide ok vs empty (that's SignalResult's job, see B2).
_RECORD_COUNT_FIELD = {
    "google_trends": "raw",
    "hacker_news": "hit_count",
    "product_hunt": "launch_count",
    "reddit": "post_count",
    "wellfound": "startup_count",
}


def _record_count(source: str, payload: dict) -> int:
    field = _RECORD_COUNT_FIELD.get(source)
    if not field:
        return 0
    value = payload.get(field)
    if isinstance(value, list):
        return len(value)
    if isinstance(value, int):
        return max(0, value)
    return 0


def compute_source_quality(result: SignalResult) -> float:
    """0.0-1.0. See module docstring for the rule."""
    if result.status in (SignalStatus.UNAVAILABLE, SignalStatus.RATE_LIMITED, SignalStatus.ERROR):
        return 0.0
    if result.status == SignalStatus.EMPTY:
        return _EMPTY_QUALITY

    payload = result.payload or {}
    record_count = _record_count(result.source, payload)
    bonus = min(_RECORD_COUNT_BONUS_CAP, (record_count / _RECORD_COUNT_FOR_FULL_BONUS) * _RECORD_COUNT_BONUS_CAP)
    quality = _OK_BASE_QUALITY + bonus
    if payload.get("_cached"):
        quality *= _CACHED_DISCOUNT
    return round(min(1.0, quality), 3)


def compute_report_signal_quality(signals: dict) -> tuple[float, bool, dict[str, float]]:
    """signals: the flat {"source_name": <SignalResult-shaped or legacy
    dict>, ...} map (ReportDocument.signals / GraphState["signals"]).

    Returns (report_signal_quality, low_confidence, signal_quality_by_source).
    report_signal_quality is the mean per-source quality across whichever
    sources are present. low_confidence is true when fewer than
    MIN_LIVE_SOURCES sources returned actual live data (status == ok) —
    'empty' doesn't count as live data here even though it's honest,
    since it carries no corroborating evidence either way.
    """
    per_source: dict[str, float] = {}
    live_count = 0

    for name, raw in (signals or {}).items():
        result = coerce_to_signal_result(name, raw)
        per_source[name] = compute_source_quality(result)
        if result.status == SignalStatus.OK:
            live_count += 1

    report_quality = round(sum(per_source.values()) / len(per_source), 3) if per_source else 0.0
    low_confidence = live_count < MIN_LIVE_SOURCES
    return report_quality, low_confidence, per_source
