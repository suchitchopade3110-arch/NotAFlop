"""
MongoDB (Motor) client lifecycle.
Mirrors services/cache.py's fallback idiom: a module-level availability
flag flips to False on any connection failure, and every call site checks
it first so a down/unreachable Mongo degrades the app instead of crashing
requests. Unlike cache.py, there is no in-memory fallback here — when
Mongo is unavailable, persistence is simply skipped.
"""
import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.config import MONGODB_DB, MONGODB_URI

logger = logging.getLogger("notaflop.mongo")

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None
_mongo_available = False


async def connect() -> None:
    """Call once from the FastAPI lifespan startup. Never raises."""
    global _client, _db, _mongo_available

    try:
        _client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        await _client.admin.command("ping")
        _db = _client[MONGODB_DB]
        _mongo_available = True
        logger.info("MongoDB connected (db=%s)", MONGODB_DB)
    except Exception:
        _mongo_available = False
        _db = None
        logger.error("MongoDB unreachable at startup — persistence disabled.", exc_info=True)


async def disconnect() -> None:
    global _client, _db, _mongo_available
    if _client is not None:
        _client.close()
    _client = None
    _db = None
    _mongo_available = False


def is_available() -> bool:
    return _mongo_available


def get_db() -> AsyncIOMotorDatabase | None:
    """Returns the database handle, or None if Mongo is unavailable."""
    return _db if _mongo_available else None


def mark_unavailable(exc: Exception) -> None:
    """Called by repositories when a request-time operation fails, so a
    Mongo that dies mid-run also stops being hit on every subsequent call."""
    global _mongo_available
    _mongo_available = False
    logger.error("MongoDB operation failed — persistence disabled.", exc_info=exc)
