"""
Cross-source conflict detection (Phase 1, B4). Rule-based, no LLM call —
pure functions over the SignalResult envelope (services.data_sources.result).

Only compares sources that both actually returned live data (status ==
ok): a missing, unavailable, rate-limited, or empty source is never
treated as implicitly agreeing OR disagreeing with anything — a conflict
is only raised between two sources that genuinely spoke, so this never
invents a disagreement out of missing data.

Purely a disclosure layer, like signal_quality (B3): conflicts are
recorded on the report for a reader to see, never fed back into
aggregate_results, WEIGHTS, or the gate.

Known limitation, not something this module papers over: the rules below
key on categorical fields (google_trends.trend, reddit.pain_frequency,
hacker_news.founder_pain_signal, product_hunt.market_signal) that today's
live fetchers (services/data_sources/*.py _fetch_live()) don't actually
populate yet — only their unused _stub() functions define that vocabulary.
Until a live fetcher starts returning one of these fields, the detector
correctly finds nothing to compare and reports zero conflicts for that
pair, rather than guessing a direction from data that isn't there.
"""
from dataclasses import dataclass, field

from services.data_sources.result import SignalResult, SignalStatus, coerce_to_signal_result


@dataclass(frozen=True)
class Conflict:
    dimension: str
    sources: list[str]
    directions: dict[str, str] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "sources": self.sources,
            "directions": self.directions,
            "description": self.description,
        }


def _live_payload(results: dict[str, SignalResult], source: str) -> dict | None:
    result = results.get(source)
    if result is None or result.status != SignalStatus.OK:
        return None
    return result.payload or {}


def _detect_trend_vs_pain(results: dict[str, SignalResult]) -> list[Conflict]:
    """google_trends.trend (rising/declining) against reddit.pain_frequency
    and hacker_news.founder_pain_signal (high/low) — declining interest
    with high current pain, or rising interest with low pain, is worth a
    reader's attention rather than quietly averaging out."""
    trends_payload = _live_payload(results, "google_trends")
    if trends_payload is None:
        return []
    trend = trends_payload.get("trend")
    if trend not in ("rising", "declining"):
        return []

    conflicts: list[Conflict] = []
    for pain_source, pain_field in (("reddit", "pain_frequency"), ("hacker_news", "founder_pain_signal")):
        payload = _live_payload(results, pain_source)
        if payload is None:
            continue
        pain = payload.get(pain_field)
        if pain not in ("high", "low"):
            continue

        pretty_source = pain_source.replace("_", " ")
        if trend == "declining" and pain == "high":
            conflicts.append(Conflict(
                dimension="interest_vs_pain",
                sources=["google_trends", pain_source],
                directions={"google_trends": "declining", pain_source: "high pain"},
                description=(
                    f"Google Trends shows declining search interest while {pretty_source} "
                    "shows high pain-mention volume for the same keyword."
                ),
            ))
        elif trend == "rising" and pain == "low":
            conflicts.append(Conflict(
                dimension="interest_vs_pain",
                sources=["google_trends", pain_source],
                directions={"google_trends": "rising", pain_source: "low pain"},
                description=(
                    f"Google Trends shows rising search interest while {pretty_source} "
                    "shows low pain-mention volume — rising interest may not reflect real pain."
                ),
            ))
    return conflicts


def _detect_saturation_vs_pain(results: dict[str, SignalResult]) -> list[Conflict]:
    """product_hunt.market_signal == 'saturated' against reddit's
    pain_frequency == 'high' — a crowded market that hasn't actually
    solved the problem, or two sources just disagreeing."""
    ph_payload = _live_payload(results, "product_hunt")
    reddit_payload = _live_payload(results, "reddit")
    if ph_payload is None or reddit_payload is None:
        return []

    if ph_payload.get("market_signal") == "saturated" and reddit_payload.get("pain_frequency") == "high":
        return [Conflict(
            dimension="market_saturation_vs_pain",
            sources=["product_hunt", "reddit"],
            directions={"product_hunt": "saturated", "reddit": "high pain"},
            description=(
                "Product Hunt shows a saturated market for this space while Reddit shows high "
                "pain-mention volume — existing products may not be solving the underlying problem."
            ),
        )]
    return []


_DETECTORS = (_detect_trend_vs_pain, _detect_saturation_vs_pain)


def detect_conflicts(signals: dict) -> list[dict]:
    """signals: the flat {"source_name": <SignalResult-shaped or legacy
    dict>, ...} map (same input shape as
    services.signal_quality.compute_report_signal_quality). Returns a
    list of conflict dicts (dimension, sources, directions, description),
    possibly empty."""
    results = {name: coerce_to_signal_result(name, raw) for name, raw in (signals or {}).items()}

    conflicts: list[Conflict] = []
    for detector in _DETECTORS:
        conflicts.extend(detector(results))
    return [c.to_dict() for c in conflicts]
