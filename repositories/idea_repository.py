"""
The only module allowed to talk to the `ideas` Motor collection directly.

`idea_hash` is indexed for analysis only, never as a cache short-circuit
(see A2/models.documents.IdeaDocument docstring) — no read path here
looks an idea up BY idea_hash to reuse or merge it with another founder's
log; every idea a founder promotes gets its own document and its own
independent score history, even if the pitch text is byte-identical to
someone else's.
"""
from datetime import datetime, timezone

from pymongo import ASCENDING
from pymongo.errors import PyMongoError

from core.logging import get_logger
from models.documents import IdeaDocument, MilestoneRecord
from services import mongo

logger = get_logger("notaflop.repositories.idea")

COLLECTION_NAME = "ideas"


def _collection():
    db = mongo.get_db()
    return db[COLLECTION_NAME] if db is not None else None


async def ensure_indexes() -> None:
    coll = _collection()
    if coll is None:
        return
    try:
        await coll.create_index([("idea_id", ASCENDING)], unique=True)
        await coll.create_index([("session_id", ASCENDING)])
        await coll.create_index([("account_id", ASCENDING)])
        await coll.create_index([("share_token", ASCENDING)], unique=True)
        await coll.create_index([("idea_hash", ASCENDING)])
    except PyMongoError:
        mongo.mark_unavailable(RuntimeError("index creation failed on ideas"))


async def create_idea(doc: IdeaDocument) -> bool:
    coll = _collection()
    if coll is None:
        logger.warning("idea_not_persisted", idea_id=doc.idea_id, status="unavailable")
        return False
    try:
        await coll.insert_one(doc.model_dump())
        return True
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


def _load(raw: dict) -> IdeaDocument:
    raw.pop("_id", None)
    return IdeaDocument.model_validate(raw)


async def get_by_id(idea_id: str) -> IdeaDocument | None:
    coll = _collection()
    if coll is None:
        return None
    try:
        raw = await coll.find_one({"idea_id": idea_id})
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None
    return _load(raw) if raw is not None else None


async def get_by_share_token(token: str) -> IdeaDocument | None:
    coll = _collection()
    if coll is None:
        return None
    try:
        raw = await coll.find_one({"share_token": token})
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None
    return _load(raw) if raw is not None else None


async def list_owned(session_id: str, account_id: str | None, limit: int = 50) -> list[IdeaDocument]:
    """Ideas owned by this caller: created under this session_id, or
    (once claimed) under this account_id. Excludes soft-deleted ideas."""
    coll = _collection()
    if coll is None:
        return []

    owner_clauses: list[dict] = [{"session_id": session_id}]
    if account_id:
        owner_clauses.append({"account_id": account_id})

    try:
        cursor = (
            coll.find({"$or": owner_clauses, "status": {"$ne": "deleted"}})
            .sort("updated_at", -1)
            .limit(limit)
        )
        raw_docs = await cursor.to_list(length=limit)
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return []
    return [_load(raw) for raw in raw_docs]


def owns(idea: IdeaDocument, session_id: str, account_id: str | None) -> bool:
    """Ownership rule shared by every /v1/ideas/* route: the calling
    session created it, or (once claimed) it belongs to the caller's
    account. An anonymous caller (no account_id) can never own an idea
    that has already been claimed onto someone else's account, even if
    it happens to share a session_id from before the claim."""
    if idea.session_id == session_id and idea.account_id is None:
        return True
    if account_id and idea.account_id == account_id:
        return True
    return False


async def set_current_snapshot(idea_id: str, snapshot_id: str) -> bool:
    coll = _collection()
    if coll is None:
        return False
    try:
        result = await coll.update_one(
            {"idea_id": idea_id},
            {
                "$set": {
                    "current_snapshot_id": snapshot_id,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.matched_count > 0
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


async def delete_idea(idea_id: str) -> bool:
    """Hard delete — B1's DELETE /v1/ideas/{id} is retention compliance,
    not an archive. Snapshots/criteria/evidence for this idea_id are
    deleted by the caller (services.log_service) in the same operation,
    since this module only owns `ideas`."""
    coll = _collection()
    if coll is None:
        return False
    try:
        result = await coll.delete_one({"idea_id": idea_id})
        return result.deleted_count > 0
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


async def transfer_to_account(session_id: str, account_id: str) -> int:
    """Claim flow: every idea created under this anonymous session_id
    (and not already claimed elsewhere) becomes owned by account_id."""
    coll = _collection()
    if coll is None:
        return 0
    try:
        result = await coll.update_many(
            {"session_id": session_id, "account_id": None},
            {"$set": {"account_id": account_id, "updated_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return 0


async def set_milestones(idea_id: str, milestones: list[MilestoneRecord]) -> bool:
    coll = _collection()
    if coll is None:
        return False
    try:
        result = await coll.update_one(
            {"idea_id": idea_id},
            {
                "$set": {
                    "milestones": [m.model_dump() for m in milestones],
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.matched_count > 0
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


async def update_milestone(idea_id: str, milestone_id: str, **fields) -> bool:
    """$set on the matched array element only — routers.phase2_milestones
    reads the idea back afterward for the response, so this just needs to
    report whether the array element was actually found and updated."""
    coll = _collection()
    if coll is None:
        return False
    set_fields = {f"milestones.$.{key}": value for key, value in fields.items()}
    set_fields["updated_at"] = datetime.now(timezone.utc)
    try:
        result = await coll.update_one(
            {"idea_id": idea_id, "milestones.milestone_id": milestone_id},
            {"$set": set_fields},
        )
        return result.matched_count > 0
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False
