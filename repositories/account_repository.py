"""
The only module allowed to talk to the `accounts` Motor collection
directly. Mirrors report_repository/session_repository's fallback idiom:
returns None/False (never raises) when Mongo is unavailable.
"""
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from core.logging import get_logger
from models.documents import AccountDocument
from services import mongo

logger = get_logger("notaflop.repositories.account")

COLLECTION_NAME = "accounts"


def _collection():
    db = mongo.get_db()
    return db[COLLECTION_NAME] if db is not None else None


async def ensure_indexes() -> None:
    coll = _collection()
    if coll is None:
        return
    try:
        await coll.create_index([("account_id", ASCENDING)], unique=True)
        await coll.create_index([("email", ASCENDING)], unique=True)
    except PyMongoError:
        mongo.mark_unavailable(RuntimeError("index creation failed on accounts"))


async def create_account(doc: AccountDocument) -> bool:
    """Rejects (returns False) if the email is already registered.

    Checked at the application level rather than relying solely on the
    unique index / DuplicateKeyError — mongomock (used in tests) doesn't
    enforce unique indexes, and this keeps behavior identical against a
    real MongoDB and the test double alike."""
    coll = _collection()
    if coll is None:
        return False
    try:
        existing = await coll.find_one({"email": doc.email})
        if existing is not None:
            return False
        await coll.insert_one(doc.model_dump())
        return True
    except DuplicateKeyError:
        return False
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


async def get_by_email(email: str) -> AccountDocument | None:
    coll = _collection()
    if coll is None:
        return None
    try:
        raw = await coll.find_one({"email": email})
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None
    if raw is None:
        return None
    raw.pop("_id", None)
    return AccountDocument.model_validate(raw)


async def get_by_id(account_id: str) -> AccountDocument | None:
    coll = _collection()
    if coll is None:
        return None
    try:
        raw = await coll.find_one({"account_id": account_id})
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None
    if raw is None:
        return None
    raw.pop("_id", None)
    return AccountDocument.model_validate(raw)


async def add_session_id(account_id: str, session_id: str) -> bool:
    coll = _collection()
    if coll is None:
        return False
    try:
        result = await coll.update_one(
            {"account_id": account_id}, {"$addToSet": {"session_ids": session_id}}
        )
        return result.matched_count > 0
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False
