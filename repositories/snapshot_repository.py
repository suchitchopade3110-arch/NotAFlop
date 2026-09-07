"""
The only module allowed to talk to the `snapshots` Motor collection
directly. Even this module is not the "single writer" the task means —
constraint #6 is enforced one level up: services/log_service.py is the
only caller of this module's write functions (create_snapshot). Every
other module that wants a score written goes through log_service, never
straight to this repository.
"""
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from core.logging import get_logger
from models.documents import SnapshotDocument
from services import mongo

logger = get_logger("notaflop.repositories.snapshot")

COLLECTION_NAME = "snapshots"


def _collection():
    db = mongo.get_db()
    return db[COLLECTION_NAME] if db is not None else None


async def ensure_indexes() -> None:
    coll = _collection()
    if coll is None:
        return
    try:
        await coll.create_index([("snapshot_id", ASCENDING)], unique=True)
        await coll.create_index([("idea_id", ASCENDING)])
    except PyMongoError:
        mongo.mark_unavailable(RuntimeError("index creation failed on snapshots"))


async def create_snapshot(doc: SnapshotDocument) -> bool:
    coll = _collection()
    if coll is None:
        logger.warning("snapshot_not_persisted", snapshot_id=doc.snapshot_id, status="unavailable")
        return False
    try:
        await coll.insert_one(doc.model_dump())
        return True
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


def _load(raw: dict) -> SnapshotDocument:
    raw.pop("_id", None)
    return SnapshotDocument.model_validate(raw)


async def get_by_id(snapshot_id: str) -> SnapshotDocument | None:
    coll = _collection()
    if coll is None:
        return None
    try:
        raw = await coll.find_one({"snapshot_id": snapshot_id})
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None
    return _load(raw) if raw is not None else None


async def get_latest_for_idea(idea_id: str) -> SnapshotDocument | None:
    coll = _collection()
    if coll is None:
        return None
    try:
        raw = await coll.find_one({"idea_id": idea_id}, sort=[("created_at", DESCENDING)])
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None
    return _load(raw) if raw is not None else None


async def list_by_idea(idea_id: str, limit: int = 200) -> list[SnapshotDocument]:
    """Oldest-first — the delta timeline reads naturally top-to-bottom as
    a history, not a most-recent-first feed."""
    coll = _collection()
    if coll is None:
        return []
    try:
        cursor = coll.find({"idea_id": idea_id}).sort("created_at", ASCENDING).limit(limit)
        raw_docs = await cursor.to_list(length=limit)
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return []
    return [_load(raw) for raw in raw_docs]


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
