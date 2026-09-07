"""
The only module allowed to talk to the `criteria` Motor collection
directly.
"""
from datetime import datetime, timedelta, timezone

from pymongo import ASCENDING
from pymongo.errors import PyMongoError

from core.logging import get_logger
from models.documents import CriterionDocument
from services import mongo

logger = get_logger("notaflop.repositories.criteria")

COLLECTION_NAME = "criteria"


def _collection():
    db = mongo.get_db()
    return db[COLLECTION_NAME] if db is not None else None


async def ensure_indexes() -> None:
    coll = _collection()
    if coll is None:
        return
    try:
        await coll.create_index([("criterion_id", ASCENDING)], unique=True)
        await coll.create_index([("idea_id", ASCENDING)])
        await coll.create_index([("deadline", ASCENDING)])
        await coll.create_index([("status", ASCENDING)])
    except PyMongoError:
        mongo.mark_unavailable(RuntimeError("index creation failed on criteria"))


async def create_criterion(doc: CriterionDocument) -> bool:
    coll = _collection()
    if coll is None:
        return False
    try:
        await coll.insert_one(doc.model_dump())
        return True
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


def _load(raw: dict) -> CriterionDocument:
    raw.pop("_id", None)
    return CriterionDocument.model_validate(raw)


async def get_by_id(criterion_id: str) -> CriterionDocument | None:
    coll = _collection()
    if coll is None:
        return None
    try:
        raw = await coll.find_one({"criterion_id": criterion_id})
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None
    return _load(raw) if raw is not None else None


async def list_by_idea(idea_id: str) -> list[CriterionDocument]:
    coll = _collection()
    if coll is None:
        return []
    try:
        cursor = coll.find({"idea_id": idea_id}).sort("deadline", ASCENDING)
        raw_docs = await cursor.to_list(length=None)
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return []
    return [_load(raw) for raw in raw_docs]


async def list_lapsable(now: datetime | None = None) -> list[CriterionDocument]:
    """Every still-pending criterion whose deadline has passed — the
    lapse sweep's input set. Silence is a signal (C3): these transition
    to `lapsed`, they are never deleted."""
    coll = _collection()
    if coll is None:
        return []
    cutoff = now or datetime.now(timezone.utc)
    try:
        cursor = coll.find({"status": "pending", "deadline": {"$lt": cutoff}})
        raw_docs = await cursor.to_list(length=None)
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return []
    return [_load(raw) for raw in raw_docs]


async def list_needing_reminder(within_days: int, now: datetime | None = None) -> list[CriterionDocument]:
    """Pending criteria whose deadline is within `within_days` and that
    haven't already had a reminder sent (C6)."""
    coll = _collection()
    if coll is None:
        return []
    now = now or datetime.now(timezone.utc)
    horizon = now + timedelta(days=within_days)
    try:
        cursor = coll.find(
            {
                "status": "pending",
                "reminder_sent_at": None,
                "deadline": {"$gte": now, "$lte": horizon},
            }
        )
        raw_docs = await cursor.to_list(length=None)
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return []
    return [_load(raw) for raw in raw_docs]


async def mark_reminder_sent(criterion_id: str) -> bool:
    coll = _collection()
    if coll is None:
        return False
    try:
        result = await coll.update_one(
            {"criterion_id": criterion_id, "reminder_sent_at": None},
            {"$set": {"reminder_sent_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


async def resolve(
    criterion_id: str, status: str, resolution_note: str | None, resolved_at: datetime | None = None
) -> bool:
    coll = _collection()
    if coll is None:
        return False
    try:
        result = await coll.update_one(
            {"criterion_id": criterion_id},
            {
                "$set": {
                    "status": status,
                    "resolution_note": resolution_note,
                    "resolved_at": resolved_at or datetime.now(timezone.utc),
                }
            },
        )
        return result.matched_count > 0
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


async def mark_lapsed(criterion_id: str) -> bool:
    coll = _collection()
    if coll is None:
        return False
    try:
        result = await coll.update_one(
            {"criterion_id": criterion_id, "status": "pending"},
            {"$set": {"status": "lapsed", "resolved_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0
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
