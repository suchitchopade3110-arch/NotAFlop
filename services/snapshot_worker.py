"""
Phase 2 re-run orchestration (C1). Runs a REDUCED agent set for one
snapshot, tracks its own Groq cost via the same per-run ledger the v1
orchestrator uses (services.cost_tracking), and writes the result
through services.log_service.record_snapshot — the only writer of
`snapshots` (constraint #6). Never touches WEIGHTS, agent prompts, or
score anchors (constraint #7): the dimension agents run here are the
exact same agents.specialist_agents instances the v1 pipeline uses,
unmodified, and scoring goes through the same services.gate arithmetic
via log_service.

Re-run set is a cost decision (task C1), not a simplification:
  - ALWAYS_RERUN_DIMENSIONS: cheap, non-LLM data layer refresh (Smart
    Data Layer) + the three dimensions genuinely sensitive to market
    movement (Timing, TAM, Moat). Runs on the schedule AND on a
    founder's manual "force re-run" — forcing a re-run just runs the
    always-eligible set sooner, it doesn't unlock the evidence-gated one.
  - EVIDENCE_GATED_DIMENSIONS: re-run ONLY when the founder submits
    evidence (C4) — never on a schedule, and never refreshes the data
    layer (it reuses the previous snapshot's signals rather than paying
    for a fresh fetch it didn't ask for).
  - NEVER_RERUN_DIMENSIONS (informational): risk, yc_signal, lovers_test
    — they describe the pitch itself, not the market or new evidence, so
    nothing in Phase 2 ever re-runs them past the initial snapshot.
"""
import asyncio

from agents.specialist_agents import ALL_AGENTS
from core.logging import get_logger
from models.documents import IdeaDocument, SnapshotDocument
from orchestrator.state import AgentOutput
from services import cost_tracking, log_service
from services.conflict_detector import detect_conflicts
from services.signal_quality import compute_report_signal_quality
from services.smart_data_layer import gather_signals

logger = get_logger("notaflop.snapshot_worker")

_AGENTS_BY_NAME = {agent.name: agent for agent in ALL_AGENTS}

ALWAYS_RERUN_DIMENSIONS = ["timing", "tam", "moat"]
EVIDENCE_GATED_DIMENSIONS = ["problem", "solution", "team", "unit_economics", "gtm", "ask"]
NEVER_RERUN_DIMENSIONS = ["risk", "yc_signal", "lovers_test"]


async def _run_dimensions(dims: list[str], transcript: str, signals: dict) -> dict[str, int]:
    agents_to_run = [_AGENTS_BY_NAME[name] for name in dims if name in _AGENTS_BY_NAME]
    state = {"transcript": transcript, "signals": signals}
    outputs: list[AgentOutput] = await asyncio.gather(
        *(agent.run(state) for agent in agents_to_run), return_exceptions=True
    )

    scores: dict[str, int] = {}
    for agent, output in zip(agents_to_run, outputs):
        if isinstance(output, Exception):
            logger.error("snapshot_dimension_failed", agent=agent.name, status="error", exc_info=output)
            continue
        scores[agent.name] = output["score"]
    return scores


async def _run_market_sensitive(idea: IdeaDocument, trigger: str) -> SnapshotDocument | None:
    """The always-re-run set: refresh Smart Data Layer signals, then
    Timing/TAM/Moat against the fresh signals."""
    cost_tracking.start_cost_tracking()

    # gather_signals() returns {"keyword": ..., "signals": {source: ...}}
    # — the flat {source: SignalResult} map is what every consumer here
    # (signal_quality, conflict_detector, agent.run's state, and
    # ReportDocument/SnapshotDocument.signals) actually expects, same as
    # v1's AnalyzeRequest.signals.
    gathered = await gather_signals(idea.keyword or idea.normalized_text)
    signals = gathered.get("signals", {})
    signal_quality, _low_confidence, _by_source = compute_report_signal_quality(signals)
    conflicts = detect_conflicts(signals)

    updated_scores = await _run_dimensions(ALWAYS_RERUN_DIMENSIONS, idea.raw_text, signals)
    cost = cost_tracking.get_total_cost_usd()

    return await log_service.record_snapshot(
        idea,
        trigger=trigger,
        updated_scores=updated_scores,
        sources=sorted(signals.keys()),
        signals=signals,
        signal_quality=signal_quality,
        conflicts=conflicts,
        cost=cost,
    )


async def run_scheduled_snapshot(idea: IdeaDocument) -> SnapshotDocument | None:
    return await _run_market_sensitive(idea, "scheduled")


async def run_manual_snapshot(idea: IdeaDocument) -> SnapshotDocument | None:
    """POST /v1/ideas/{id}/snapshots — same always-re-run set as the
    scheduler, just run on demand instead of waiting for the window."""
    return await _run_market_sensitive(idea, "manual")


async def run_evidence_snapshot(idea: IdeaDocument, evidence_context: str) -> SnapshotDocument | None:
    """C4's evidence-gated re-run: the six agents whose scores can only
    move when the founder produces proof. Reuses the previous snapshot's
    signals rather than refreshing the data layer — that's the
    always-re-run set's job, not evidence's.

    `evidence_context` is appended to the transcript text handed to
    these agents' build_user_message (never to the agent's own prompt —
    constraint #7 stays untouched): the agent reads it as part of "the
    founder pitch", exactly like any other transcript content."""
    previous = await log_service.get_latest_snapshot(idea.idea_id)
    if previous is None:
        logger.error("evidence_snapshot_no_previous", idea_id=idea.idea_id, status="skipped")
        return None

    cost_tracking.start_cost_tracking()
    transcript_with_evidence = (
        f"{idea.raw_text}\n\nAdditional evidence submitted by the founder since the last "
        f"validation:\n{evidence_context}"
    )
    updated_scores = await _run_dimensions(
        EVIDENCE_GATED_DIMENSIONS, transcript_with_evidence, previous.signals
    )
    cost = cost_tracking.get_total_cost_usd()

    return await log_service.record_snapshot(
        idea, trigger="evidence", updated_scores=updated_scores, cost=cost,
    )
