"""
The single writer for every persisted score past the v1 pipeline
(constraint #6). `reports`/`sessions` stay exactly as orchestrator/graph.py
already writes them — untouched, v1, out of scope here. This module owns
everything downstream of "a founder promoted a completed report into a
durable idea log": the `ideas` and `snapshots` collections, and the delta
math that runs at every snapshot write (C2).

No other module calls repositories.snapshot_repository.create_snapshot —
routers and the snapshot worker (C1) call record_snapshot() here, never
the repository directly. Also the natural place for idea lifecycle
writes (promote/delete/claim-transfer/milestones) since those all touch
the same "idea documents ... and score history" the task assigns here.

Score-movement discipline (C5's core rule, enforced structurally, not
just tested): record_snapshot() takes `updated_scores` — ONLY the
dimensions actually re-run for this trigger. Every other dimension is
carried forward byte-for-byte from the previous snapshot. There is no
code path here that recomputes a dimension's score without a caller
explicitly re-running that dimension's agent and passing its new score
in. Reading an idea, editing its raw_text, or time passing never calls
this function at all.
"""
from datetime import datetime, timezone
from typing import Literal

from core.ids import generate_idea_id, generate_snapshot_id
from core.logging import get_logger
from models.documents import IdeaDocument, ReportDocument, SnapshotDocument
from repositories import (
    criteria_repository,
    evidence_repository,
    idea_repository,
    report_repository,
    snapshot_repository,
)
from services.gate import WEIGHTS_VERSION, aggregate_results
from core.config import SNAPSHOT_COST_WARN_THRESHOLD_USD

logger = get_logger("notaflop.log_service")


# ── Idea lifecycle ────────────────────────────────────────────────────

async def promote_report_to_idea(
    report: ReportDocument, *, session_id: str, account_id: str | None, share_token: str
) -> IdeaDocument | None:
    """Promotes a completed, already-persisted v1 report into a durable
    idea log: one IdeaDocument + one `initial` SnapshotDocument that
    mirrors the report's own already-computed score/verdict/weights_version
    exactly (no recomputation — the report is the source of truth for the
    run that produced it). Rolls back the idea if the initial snapshot
    can't be written, so an idea is never left without a snapshot to
    build history on top of."""
    idea = IdeaDocument(
        idea_id=generate_idea_id(),
        session_id=session_id,
        account_id=account_id,
        idea_hash=report.idea_hash,
        raw_text=report.transcript,
        normalized_text=report_repository.normalize_idea(report.transcript),
        keyword=report.keyword,
        share_token=share_token,
        source_report_id=report.public_id,
    )
    if not await idea_repository.create_idea(idea):
        return None

    snapshot = SnapshotDocument(
        snapshot_id=generate_snapshot_id(),
        idea_id=idea.idea_id,
        session_id=idea.session_id,
        account_id=idea.account_id,
        agent_scores={name: record.score for name, record in report.agent_results.items()},
        raw_score=report.raw_score,
        adjusted_score=report.adjusted_score,
        verdict=report.verdict,
        weights_version=report.weights_version,
        sources=sorted(report.signals.keys()),
        signals=report.signals,
        signal_quality=report.signal_quality,
        conflicts=report.conflicts,
        trigger="initial",
        deltas={},
        version_crossing=False,
        cost=0.0,
    )
    if not await snapshot_repository.create_snapshot(snapshot):
        await idea_repository.delete_idea(idea.idea_id)
        logger.error("idea_promotion_rolled_back", idea_id=idea.idea_id, status="snapshot_write_failed")
        return None

    await idea_repository.set_current_snapshot(idea.idea_id, snapshot.snapshot_id)
    idea.current_snapshot_id = snapshot.snapshot_id  # reflect the write in the returned object too
    logger.info("idea_promoted", idea_id=idea.idea_id, source_report_id=report.public_id, status="ok")
    return idea


async def get_idea(idea_id: str) -> IdeaDocument | None:
    return await idea_repository.get_by_id(idea_id)


async def get_idea_by_share_token(token: str) -> IdeaDocument | None:
    return await idea_repository.get_by_share_token(token)


async def list_owned_ideas(session_id: str, account_id: str | None) -> list[IdeaDocument]:
    return await idea_repository.list_owned(session_id, account_id)


def owns_idea(idea: IdeaDocument, session_id: str, account_id: str | None) -> bool:
    return idea_repository.owns(idea, session_id, account_id)


async def delete_idea_cascade(idea_id: str) -> bool:
    """Retention-compliance delete (B1 DELETE /v1/ideas/{id}) — removes
    every document across every collection this module owns for that
    idea, not just the idea itself."""
    await snapshot_repository.delete_by_idea(idea_id)
    await criteria_repository.delete_by_idea(idea_id)
    await evidence_repository.delete_by_idea(idea_id)
    return await idea_repository.delete_idea(idea_id)


async def claim_ideas(session_id: str, account_id: str) -> int:
    """A4's claim flow: every idea created under this anonymous session
    that hasn't already been claimed becomes owned by account_id."""
    return await idea_repository.transfer_to_account(session_id, account_id)


# ── Score history ─────────────────────────────────────────────────────

async def get_snapshot_history(idea_id: str) -> list[SnapshotDocument]:
    return await snapshot_repository.list_by_idea(idea_id)


async def get_latest_snapshot(idea_id: str) -> SnapshotDocument | None:
    return await snapshot_repository.get_latest_for_idea(idea_id)


async def record_snapshot(
    idea: IdeaDocument,
    *,
    trigger: Literal["scheduled", "evidence", "manual"],
    updated_scores: dict[str, int],
    sources: list[str] | None = None,
    signals: dict | None = None,
    signal_quality: float | None = None,
    conflicts: list[dict] | None = None,
    cost: float = 0.0,
) -> SnapshotDocument | None:
    """The one place a re-score is written, for every trigger past the
    idea's `initial` snapshot (C1's scheduled worker, C4's evidence
    submission, C3's kill-criterion resolution, C7's internal re-score).

    `updated_scores` carries ONLY the dimensions this run actually
    re-scored — everything else is carried forward unchanged from the
    previous snapshot (see module docstring: this is what makes "the
    score moves only on evidence" true by construction, not just by
    convention). weights_version is always the CURRENT gate.WEIGHTS_VERSION,
    stamped fresh at this write (constraint #4) — never inferred from the
    previous snapshot; `version_crossing` records when that differs from
    the snapshot being diffed against, so a delta across a weights change
    is never presented as a like-for-like movement.

    Returns None (no-op, logged) if there's no previous snapshot to build
    on, or if the write itself fails — current_snapshot_id is only ever
    advanced after a successful write, so a failed re-run can't corrupt
    it (constraint: idempotent per idea per window, never a partial
    write)."""
    previous = await snapshot_repository.get_latest_for_idea(idea.idea_id)
    if previous is None:
        logger.error("record_snapshot_no_previous_snapshot", idea_id=idea.idea_id, status="skipped")
        return None

    merged_scores = {**previous.agent_scores, **updated_scores}
    results_for_gate = {name: {"score": score} for name, score in merged_scores.items()}
    raw_score, verdict = aggregate_results(results_for_gate)

    version_crossing = previous.weights_version != WEIGHTS_VERSION

    # C2: per-dimension scores (0-10) mean the same thing regardless of
    # WEIGHTS_VERSION — only the WEIGHTS themselves changed, not the
    # rubric each agent scores against — so "dimensions" stays a
    # meaningful like-for-like diff even across a weights change. The
    # aggregate raw_score delta is the one that can be misleading (the
    # same dimension scores can produce a different aggregate purely
    # from a weights change, with nothing in the market or evidence
    # having moved) — version_crossing flags exactly that, and
    # weights_version is stored on BOTH sides of the comparison so a
    # reader never has to guess which weighting produced which number.
    deltas = {
        "raw_score": raw_score - previous.raw_score,
        "dimensions": {
            dim: merged_scores[dim] - previous.agent_scores[dim]
            for dim in updated_scores
            if dim in previous.agent_scores
        },
        "previous_weights_version": previous.weights_version,
        "current_weights_version": WEIGHTS_VERSION,
    }

    snapshot = SnapshotDocument(
        snapshot_id=generate_snapshot_id(),
        idea_id=idea.idea_id,
        session_id=idea.session_id,
        account_id=idea.account_id,
        agent_scores=merged_scores,
        raw_score=raw_score,
        # Phase 2 re-runs never invoke the Verifier — it's outside every
        # re-run set C1 defines — so adjusted_score mirrors raw_score
        # rather than going stale at whatever the last report computed.
        adjusted_score=raw_score,
        verdict=verdict,
        weights_version=WEIGHTS_VERSION,
        sources=sources if sources is not None else previous.sources,
        signals=signals if signals is not None else previous.signals,
        signal_quality=signal_quality if signal_quality is not None else previous.signal_quality,
        conflicts=conflicts if conflicts is not None else previous.conflicts,
        trigger=trigger,
        deltas=deltas,
        version_crossing=version_crossing,
        cost=cost,
    )

    saved = await snapshot_repository.create_snapshot(snapshot)
    if not saved:
        logger.warning("snapshot_not_persisted", idea_id=idea.idea_id, status="unavailable")
        return None

    await idea_repository.set_current_snapshot(idea.idea_id, snapshot.snapshot_id)

    logger.info(
        "snapshot_recorded",
        idea_id=idea.idea_id, snapshot_id=snapshot.snapshot_id, trigger=trigger,
        cost_usd=cost, raw_score=raw_score, status="ok",
    )
    if cost > SNAPSHOT_COST_WARN_THRESHOLD_USD:
        logger.warning(
            "snapshot_cost_over_target",
            idea_id=idea.idea_id, snapshot_id=snapshot.snapshot_id,
            cost_usd=cost, target_usd=SNAPSHOT_COST_WARN_THRESHOLD_USD,
        )

    return snapshot
