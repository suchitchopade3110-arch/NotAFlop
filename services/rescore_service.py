"""
Internal retroactive re-scoring (C7, POST /internal/rescore — admin
only). Recomputes raw_score/verdict for an idea's LATEST snapshot's
already-known agent_scores under the CURRENT services.gate.WEIGHTS_VERSION
/ WEIGHTS — no agent is re-run and no signal is re-fetched, so this costs
nothing beyond gate.aggregate_results' own arithmetic (constraint #7:
WEIGHTS themselves are never touched by this or anything else).

Writes a NEW snapshot through services.log_service.record_snapshot
(trigger='manual', empty updated_scores — every dimension carries
forward unchanged, only the weighting the aggregate is computed under
changes). Historical snapshots are never mutated (constraint: "Writes
new snapshots; never mutates historical ones").

Skips (writes nothing for) an idea whose latest snapshot is already
stamped at the current WEIGHTS_VERSION — there's nothing retroactive to
apply.
"""
from core.logging import get_logger
from models.documents import IdeaDocument
from repositories import idea_repository
from services import log_service
from services.gate import WEIGHTS_VERSION

logger = get_logger("notaflop.rescore_service")


async def rescore_idea(idea: IdeaDocument) -> tuple[str, str | None]:
    """Returns (status, snapshot_id) — status is one of 'rescored',
    'skipped_no_change', or 'failed'."""
    latest = await log_service.get_latest_snapshot(idea.idea_id)
    if latest is None:
        logger.error("rescore_no_previous_snapshot", idea_id=idea.idea_id, status="failed")
        return "failed", None

    if latest.weights_version == WEIGHTS_VERSION:
        return "skipped_no_change", None

    snapshot = await log_service.record_snapshot(idea, trigger="manual", updated_scores={})
    if snapshot is None:
        return "failed", None

    logger.info(
        "idea_rescored", idea_id=idea.idea_id, snapshot_id=snapshot.snapshot_id,
        from_weights_version=latest.weights_version, to_weights_version=WEIGHTS_VERSION, status="ok",
    )
    return "rescored", snapshot.snapshot_id


async def rescore_all_active() -> list[tuple[str, str, str | None]]:
    """Returns a list of (idea_id, status, snapshot_id) — the sweep form
    of POST /internal/rescore when no idea_id is supplied."""
    results: list[tuple[str, str, str | None]] = []
    for idea in await idea_repository.list_active():
        status, snapshot_id = await rescore_idea(idea)
        results.append((idea.idea_id, status, snapshot_id))
    return results
