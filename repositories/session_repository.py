"""
The only module allowed to talk to the `sessions` Motor collection directly.
"""
import logging
from datetime import datetime, timedelta, timezone

from pymongo import ASCENDING
from pymongo.errors import PyMongoError

from models.documents import SessionDocument
from services import mongo

logger = logging.getLogger("notaflop.repositories.session")

COLLECTION_NAME = "sessions"
SESSION_TTL_DAYS = 30


def _collection():
    db = mongo.get_db()
    return db[COLLECTION_NAME] if db is not None else None


async def ensure_indexes() -> None:
    coll = _collection()
    if coll is None:
        return
    try:
        await coll.create_index([("session_id", ASCENDING)], unique=True)
        await coll.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    except PyMongoError:
        mongo.mark_unavailable(RuntimeError("index creation failed on sessions"))


async def get_or_create_session(session_id: str, ip: str | None) -> SessionDocument | None:
    """Touches last_seen_at/expires_at on every call — sessions stay alive
    (sliding TTL) as long as they're actively used."""
    coll = _collection()
    if coll is None:
        return None

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=SESSION_TTL_DAYS)

    try:
        raw = await coll.find_one_and_update(
            {"session_id": session_id},
            {
                "$set": {"last_seen_at": now, "expires_at": expires_at},
                "$setOnInsert": {
                    "session_id": session_id,
                    "ip": ip,
                    "created_at": now,
                    "report_count": 0,
                },
            },
            upsert=True,
            return_document=True,
        )
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None

    if raw is None:
        return None
    raw.pop("_id", None)
    return SessionDocument.model_validate(raw)


async def increment_report_count(session_id: str) -> None:
    coll = _collection()
    if coll is None:
        return
    try:
        await coll.update_one({"session_id": session_id}, {"$inc": {"report_count": 1}})
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)


async def get_session(session_id: str) -> SessionDocument | None:
    coll = _collection()
    if coll is None:
        return None
    try:
        raw = await coll.find_one({"session_id": session_id})
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None
    if raw is None:
        return None
    raw.pop("_id", None)
    return SessionDocument.model_validate(raw)
