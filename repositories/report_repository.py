"""
The only module allowed to talk to the `reports` Motor collection directly.
Routers and the orchestrator go through here, never through services.mongo
or Motor collections themselves.
"""
import hashlib
import re

from pymongo import ASCENDING
from pymongo.errors import PyMongoError

from core.logging import get_logger
from models.documents import ReportDocument, VerifierOutput
from services import mongo

logger = get_logger("notaflop.repositories.report")

COLLECTION_NAME = "reports"

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_idea(text: str) -> str:
    """
    Stable normalization for idea_hash. Rule (frozen — changing this
    invalidates every existing idea_hash and would need a backfill if
    short-circuiting is ever built on top of it):

      1. Unicode-lowercase the full string.
      2. Strip all punctuation (anything not a word character or
         whitespace, per Python's \\w — this keeps letters/digits/
         underscore across scripts, drops periods/commas/quotes/etc).
      3. Collapse any run of whitespace to a single ASCII space.
      4. Strip leading/trailing whitespace.

    Two pitches that differ only in casing, punctuation, or spacing
    normalize to the same string and therefore the same idea_hash.
    """
    lowered = text.lower()
    no_punct = _PUNCT_RE.sub(" ", lowered)
    collapsed = _WHITESPACE_RE.sub(" ", no_punct)
    return collapsed.strip()


def compute_idea_hash(text: str) -> str:
    normalized = normalize_idea(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def _collection():
    db = mongo.get_db()
    return db[COLLECTION_NAME] if db is not None else None


async def ensure_indexes() -> None:
    coll = _collection()
    if coll is None:
        return
    try:
        await coll.create_index([("public_id", ASCENDING)], unique=True)
        await coll.create_index([("idea_hash", ASCENDING)])
        await coll.create_index([("session_id", ASCENDING)])
        await coll.create_index([("account_id", ASCENDING)])
    except PyMongoError:
        mongo.mark_unavailable(RuntimeError("index creation failed on reports"))


async def create_report(doc: ReportDocument) -> bool:
    """Persists a report. Returns False (no-op, logged) if Mongo is down.

    Also logs whether this idea_hash has been seen before and how many
    times — index-only for now (no short-circuiting), purely to measure
    whether short-circuiting would be worth building later.
    """
    coll = _collection()
    if coll is None:
        logger.warning("report_not_persisted", public_id=doc.public_id, status="unavailable")
        return False

    try:
        prior_count = await coll.count_documents({"idea_hash": doc.idea_hash})
        logger.info(
            "idea_hash_hit_rate",
            hash=doc.idea_hash, prior_count=prior_count, is_repeat=prior_count > 0,
        )
        await coll.insert_one(doc.model_dump())
        return True
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False


async def get_by_public_id(public_id: str) -> ReportDocument | None:
    coll = _collection()
    if coll is None:
        return None

    try:
        raw = await coll.find_one({"public_id": public_id})
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return None

    if raw is None:
        return None
    raw.pop("_id", None)
    return ReportDocument.model_validate(raw)


async def list_by_session(session_id: str, limit: int = 20) -> list[ReportDocument]:
    coll = _collection()
    if coll is None:
        return []

    try:
        cursor = coll.find({"session_id": session_id}).sort("created_at", -1).limit(limit)
        raw_docs = await cursor.to_list(length=limit)
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return []

    results = []
    for raw in raw_docs:
        raw.pop("_id", None)
        results.append(ReportDocument.model_validate(raw))
    return results


_DIVERGENCE_BUCKETS: list[tuple[str, int, int]] = [
    # (label, low, high) — inclusive on both ends, in absolute-delta points.
    ("0", 0, 0),
    ("1-5", 1, 5),
    ("6-10", 6, 10),
    ("11-20", 11, 20),
    ("21+", 21, 100),
]


def _bucket_for(delta: int) -> str:
    for label, low, high in _DIVERGENCE_BUCKETS:
        if low <= delta <= high:
            return label
    return _DIVERGENCE_BUCKETS[-1][0]


async def get_verifier_divergence_stats() -> dict:
    """Shadow-mode divergence between raw_score and adjusted_score across
    every stored snapshot that has a Verifier result. Read-only — computes
    nothing that feeds back into gating; purely observability for A2.

    Returns count=0 / mean=0.0 / max=0 / empty buckets when Mongo is down
    or no snapshot has a Verifier result yet, rather than raising.
    """
    coll = _collection()
    empty = {
        "count": 0,
        "mean_absolute_delta": 0.0,
        "max_delta": 0,
        "distribution": {label: 0 for label, _, _ in _DIVERGENCE_BUCKETS},
    }
    if coll is None:
        return empty

    try:
        cursor = coll.find(
            {"adjusted_score": {"$ne": None}, "verifier": {"$ne": None}},
            {"raw_score": 1, "adjusted_score": 1},
        )
        docs = await cursor.to_list(length=None)
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return empty

    deltas = [
        abs(doc["raw_score"] - doc["adjusted_score"])
        for doc in docs
        if doc.get("raw_score") is not None and doc.get("adjusted_score") is not None
    ]
    if not deltas:
        return empty

    distribution = {label: 0 for label, _, _ in _DIVERGENCE_BUCKETS}
    for delta in deltas:
        distribution[_bucket_for(delta)] += 1

    return {
        "count": len(deltas),
        "mean_absolute_delta": round(sum(deltas) / len(deltas), 2),
        "max_delta": max(deltas),
        "distribution": distribution,
    }


async def patch_verifier(
    public_id: str,
    verifier: VerifierOutput,
    adjusted_score: int,
    verdict_would_flip: bool,
    *,
    additional_cost_usd: float = 0.0,
) -> bool:
    """Fire-and-forget patch applied once the Verifier lands after the
    report has already streamed and been persisted (shadow mode).

    additional_cost_usd (C3): shadow mode runs the Verifier's Groq call in
    a task spawned AFTER the report's initial report_cost_usd was already
    read and persisted (see orchestrator.graph._spawn_verifier_shadow), so
    that initial total doesn't include it — $inc adds it on here rather
    than $set overwriting whatever the field already held."""
    coll = _collection()
    if coll is None:
        return False

    update: dict = {
        "$set": {
            "verifier": verifier.model_dump(),
            "adjusted_score": adjusted_score,
            "verdict_would_flip": verdict_would_flip,
        }
    }
    if additional_cost_usd:
        update["$inc"] = {"report_cost_usd": additional_cost_usd}

    try:
        result = await coll.update_one({"public_id": public_id}, update)
        return result.modified_count > 0
    except PyMongoError as exc:
        mongo.mark_unavailable(exc)
        return False
