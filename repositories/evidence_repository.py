"""
The only module allowed to talk to the `evidence` Motor collection
directly.
"""
from pymongo import ASCENDING
from pymongo.errors import PyMongoError

from core.logging import get_logger
from models.documents import EvidenceDocument
from services import mongo

logger = get_logger("notaflop.repositories.evidence")

COLLECTION_NAME = "evidence"


def _collection():
    db = mongo.get_db()
    return db[COLLECTION_NAME] if db is not None else None


async def ensure_indexes() -> None:
    coll = _collection()
    if coll is None:
        return
    try:
        await coll.create_index([("evidence_id", ASCENDING)], unique=True)
        await coll.create_index([("idea_id", ASCENDING)])
        await coll.create_index([("session_id", ASCENDING)])
        await coll.create_index([("account_id", ASCENDING)])
    except PyMongoError:
        mongo.mark_unavailable(RuntimeError("index creation failed on evidence"))


async def create_evidence(doc: EvidenceDocument) -> bool:
    coll = _collection()
    if coll is None:
        return False
    try:
        await coll.insert_one(doc.model_dump())
        return True
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


def _load(raw: dict) -> EvidenceDocument:
    raw.pop("_id", None)
    return EvidenceDocument.model_validate(raw)


async def get_by_id(evidence_id: str) -> EvidenceDocument | None:
    coll = _collection()
    if coll is None:
        return None
    try:
        raw = await coll.find_one({"evidence_id": evidence_id})
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None
    return _load(raw) if raw is not None else None


async def list_by_idea(idea_id: str) -> list[EvidenceDocument]:
    coll = _collection()
    if coll is None:
        return []
    try:
        cursor = coll.find({"idea_id": idea_id}).sort("submitted_at", ASCENDING)
        raw_docs = await cursor.to_list(length=None)
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return []
    return [_load(raw) for raw in raw_docs]


async def set_triggered_snapshot(evidence_id: str, snapshot_id: str) -> bool:
    coll = _collection()
    if coll is None:
        return False
    try:
        result = await coll.update_one(
            {"evidence_id": evidence_id}, {"$set": {"triggered_snapshot_id": snapshot_id}}
        )
        return result.matched_count > 0
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


async def delete_by_idea(idea_id: str) -> int:
    coll = _collection()
    if coll is None:
        return 0
    try:
        result = await coll.delete_many({"idea_id": idea_id})
        return result.deleted_count
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return 0
