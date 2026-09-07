"""
Kill-criteria lifecycle (C3). A criterion is a falsifiable commitment
the founder makes at validation time — met/failed on resolution, or
lapsed if its deadline passes with no resolution. Silence is a signal:
lapsing is a recorded state, never a deletion.

Resolving a criterion IS evidence: it writes an EvidenceDocument
(type='criterion_resolution') and triggers the same evidence-gated
re-score C4's evidence submission does, through
services.snapshot_worker.run_evidence_snapshot — which itself only ever
writes through services.log_service.record_snapshot (constraint #6).
"""
from core.config import CRITERIA_DEADLINE_REMINDER_DAYS
from core.ids import generate_criterion_id, generate_evidence_id
from core.logging import get_logger
from models.documents import CriterionDocument, EvidenceDocument, IdeaDocument
from models.schemas import CriterionRequest
from repositories import criteria_repository, evidence_repository, idea_repository
from services import snapshot_worker
from services.notifications import service as notifications

logger = get_logger("notaflop.criteria_service")


async def create_criterion(idea: IdeaDocument, body: CriterionRequest) -> CriterionDocument | None:
    criterion = CriterionDocument(
        criterion_id=generate_criterion_id(),
        idea_id=idea.idea_id,
        session_id=idea.session_id,
        account_id=idea.account_id,
        statement=body.statement,
        metric=body.metric,
        threshold=body.threshold,
        deadline=body.deadline,
    )
    if not await criteria_repository.create_criterion(criterion):
        return None
    return criterion


async def list_criteria(idea_id: str) -> list[CriterionDocument]:
    return await criteria_repository.list_by_idea(idea_id)


async def resolve_criterion(
    criterion: CriterionDocument, idea: IdeaDocument, outcome: str, note: str
) -> tuple[CriterionDocument, EvidenceDocument] | None:
    """Records the outcome, logs it as evidence, and re-scores the
    evidence-gated dimension set. Returns None (no-op) only if the
    status write itself fails — the evidence + re-score still happen
    best-effort even if the re-score can't complete, since the
    resolution itself is the durable record silence would otherwise
    have to stand in for."""
    if not await criteria_repository.resolve(criterion.criterion_id, outcome, note):
        return None

    evidence = EvidenceDocument(
        evidence_id=generate_evidence_id(),
        idea_id=idea.idea_id,
        session_id=idea.session_id,
        account_id=idea.account_id,
        type="criterion_resolution",
        payload={
            "criterion_id": criterion.criterion_id,
            "statement": criterion.statement,
            "metric": criterion.metric,
            "threshold": criterion.threshold,
            "outcome": outcome,
            "note": note,
        },
    )
    await evidence_repository.create_evidence(evidence)

    evidence_context = (
        f'Kill-criterion resolved: "{criterion.statement}" '
        f"(metric: {criterion.metric}, threshold: {criterion.threshold}) -> {outcome}. {note}"
    )
    snapshot = await snapshot_worker.run_evidence_snapshot(idea, evidence_context)
    if snapshot is not None:
        await evidence_repository.set_triggered_snapshot(evidence.evidence_id, snapshot.snapshot_id)
        evidence.triggered_snapshot_id = snapshot.snapshot_id  # reflect the write in the returned object

    resolved = await criteria_repository.get_by_id(criterion.criterion_id)
    return resolved, evidence


async def sweep_lapsed_criteria() -> int:
    """The lapse sweep — registered onto the background scheduler
    (services.scheduler.register_sweep, see routers/v1_criteria.py).
    Every still-pending criterion whose deadline has passed transitions
    to 'lapsed'; nothing is ever deleted."""
    lapsed_count = 0
    for criterion in await criteria_repository.list_lapsable():
        if await criteria_repository.mark_lapsed(criterion.criterion_id):
            lapsed_count += 1
    if lapsed_count:
        logger.info("criteria_lapse_sweep_complete", lapsed_count=lapsed_count, status="ok")
    return lapsed_count


async def sweep_deadline_reminders() -> int:
    """C6's other scheduled sweep: every pending criterion whose deadline
    is within CRITERIA_DEADLINE_REMINDER_DAYS gets exactly one reminder
    (mark_reminder_sent is a conditional update, so a reminder is never
    sent twice even if this sweep overlaps itself)."""
    sent_count = 0
    for criterion in await criteria_repository.list_needing_reminder(CRITERIA_DEADLINE_REMINDER_DAYS):
        idea = await idea_repository.get_by_id(criterion.idea_id)
        if idea is None:
            continue
        sent = await notifications.send_criteria_deadline_reminder(idea, criterion)
        if sent and await criteria_repository.mark_reminder_sent(criterion.criterion_id):
            sent_count += 1
    if sent_count:
        logger.info("criteria_reminder_sweep_complete", sent_count=sent_count, status="ok")
    return sent_count
