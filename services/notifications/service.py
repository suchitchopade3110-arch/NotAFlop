"""
Notification composition + dispatch (C6): magic-link auth mail,
snapshot digests, kill-criteria deadline reminders. Every function here
composes a message and hands it to the currently-configured
NotificationProvider (services.notifications.base) — default is
LoggingNotificationProvider (no-op-logging, acceptable for now).

Suppression is enforced HERE, not left to the provider or the caller:
notify_snapshot() never calls the provider at all for a no-delta
snapshot ("A monthly digest reporting that nothing moved trains the
founder to ignore the channel, which kills the return loop this whole
phase exists to build") and no notification here is ever sent to an
idea with no claimed account/email — Phase 2 never emails an anonymous
session.
"""
from core.logging import get_logger
from models.documents import CriterionDocument, IdeaDocument, SnapshotDocument
from repositories import account_repository
from services.notifications.base import NotificationProvider
from services.notifications.logging_provider import LoggingNotificationProvider

logger = get_logger("notaflop.notifications")

_provider: NotificationProvider = LoggingNotificationProvider()


def set_provider(provider: NotificationProvider) -> None:
    """Swap the active provider — call once at process startup (or from
    a test) to point every notification at a real integration instead
    of the logging default."""
    global _provider
    _provider = provider


async def _owner_email(idea: IdeaDocument) -> str | None:
    """Phase 2 never emails an unclaimed (anonymous) idea — there's no
    address to send to, and no consent to send one even if there were."""
    if not idea.account_id:
        return None
    account = await account_repository.get_by_id(idea.account_id)
    return account.email if account else None


async def send_magic_link(email: str, link: str) -> bool:
    subject = "Your NotAFlop sign-in link"
    body = (
        f"Click to claim your validation log: {link}\n\n"
        "This link is single-use and expires shortly. If you didn't request it, ignore this email."
    )
    return await _provider.send(to=email, subject=subject, body=body, kind="magic_link")


def _is_no_delta(snapshot: SnapshotDocument) -> bool:
    """A snapshot is 'no delta' when neither the aggregate score nor any
    individual dimension moved — the initial snapshot (deltas == {}, no
    predecessor to compare against) never reaches here at all since
    nothing calls notify_snapshot for an `initial` trigger."""
    if snapshot.deltas.get("raw_score", 0) != 0:
        return False
    return not any(delta != 0 for delta in snapshot.deltas.get("dimensions", {}).values())


async def notify_snapshot(idea: IdeaDocument, snapshot: SnapshotDocument) -> bool:
    """Called after a scheduled/manual/evidence snapshot is recorded
    (services.snapshot_worker). Suppressed entirely — never reaches the
    provider — when nothing moved, or when the idea has no claimed
    account to notify."""
    if _is_no_delta(snapshot):
        logger.info(
            "snapshot_digest_suppressed_no_delta",
            idea_id=idea.idea_id, snapshot_id=snapshot.snapshot_id, status="suppressed",
        )
        return False

    email = await _owner_email(idea)
    if email is None:
        logger.info(
            "snapshot_digest_suppressed_unclaimed",
            idea_id=idea.idea_id, snapshot_id=snapshot.snapshot_id, status="suppressed",
        )
        return False

    delta = snapshot.deltas.get("raw_score", 0)
    sign = "+" if delta >= 0 else ""
    subject = f"Your idea moved: {snapshot.raw_score}/100 ({sign}{delta})"
    moved_dims = ", ".join(
        f"{dim} {'+' if d >= 0 else ''}{d}" for dim, d in snapshot.deltas.get("dimensions", {}).items() if d != 0
    )
    version_note = (
        " (weighting changed since your last snapshot — treat the aggregate move with caution)"
        if snapshot.version_crossing else ""
    )
    body = (
        f"Verdict: {snapshot.verdict}. Score: {snapshot.raw_score}/100 ({sign}{delta}){version_note}.\n"
        f"What moved: {moved_dims or 'nothing at the dimension level'}."
    )
    return await _provider.send(to=email, subject=subject, body=body, kind="snapshot_digest")


async def send_criteria_deadline_reminder(idea: IdeaDocument, criterion: CriterionDocument) -> bool:
    email = await _owner_email(idea)
    if email is None:
        logger.info(
            "criteria_reminder_suppressed_unclaimed", criterion_id=criterion.criterion_id, status="suppressed",
        )
        return False

    subject = f"Kill-criterion deadline approaching: {criterion.statement}"
    body = (
        f"Metric: {criterion.metric}\nThreshold: {criterion.threshold}\n"
        f"Deadline: {criterion.deadline.isoformat()}\n\n"
        "Resolve it (met or failed) to keep your validation log honest — an unresolved "
        "criterion lapses at the deadline and is recorded as silence, not deleted."
    )
    return await _provider.send(to=email, subject=subject, body=body, kind="criteria_deadline")
