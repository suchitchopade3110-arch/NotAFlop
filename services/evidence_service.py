"""
Evidence submission (C4). Triggers the same evidence-gated re-score a
resolved kill-criterion does (C3), through
services.snapshot_worker.run_evidence_snapshot — which only ever writes
through services.log_service.record_snapshot (constraint #6). The
submitted evidence is passed into the re-run's agent context as plain
transcript text (see snapshot_worker.run_evidence_snapshot's docstring)
— never into any agent's own prompt (constraint #7).
"""
import json

from core.ids import generate_evidence_id
from models.documents import EvidenceDocument, IdeaDocument, SnapshotDocument
from models.schemas import EvidenceRequest
from repositories import evidence_repository
from services import snapshot_worker


async def submit_evidence(
    idea: IdeaDocument, body: EvidenceRequest
) -> tuple[EvidenceDocument, SnapshotDocument | None] | None:
    evidence = EvidenceDocument(
        evidence_id=generate_evidence_id(),
        idea_id=idea.idea_id,
        session_id=idea.session_id,
        account_id=idea.account_id,
        type=body.type,
        payload=body.payload,
    )
    if not await evidence_repository.create_evidence(evidence):
        return None

    evidence_context = f"{body.type.replace('_', ' ').title()} evidence: {json.dumps(body.payload)}"
    snapshot = await snapshot_worker.run_evidence_snapshot(idea, evidence_context)
    if snapshot is not None:
        await evidence_repository.set_triggered_snapshot(evidence.evidence_id, snapshot.snapshot_id)
        evidence.triggered_snapshot_id = snapshot.snapshot_id

    return evidence, snapshot
