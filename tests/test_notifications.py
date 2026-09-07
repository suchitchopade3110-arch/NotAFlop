import pytest

from models.documents import AccountDocument, CriterionDocument, IdeaDocument, SnapshotDocument
from repositories import account_repository
from services.notifications import service as notifications
from services.notifications.base import NotificationProvider
from services.notifications.logging_provider import LoggingNotificationProvider


class _RecordingProvider(NotificationProvider):
    def __init__(self):
        self.sent = []

    async def send(self, *, to, subject, body, kind):
        self.sent.append({"to": to, "subject": subject, "body": body, "kind": kind})
        return True


@pytest.fixture(autouse=True)
def _reset_provider():
    original = notifications._provider
    yield
    notifications.set_provider(original)


async def test_logging_provider_returns_true():
    provider = LoggingNotificationProvider()
    assert await provider.send(to="a@example.com", subject="s", body="b", kind="magic_link") is True


async def test_set_provider_swaps_active_provider():
    recording = _RecordingProvider()
    notifications.set_provider(recording)

    await notifications.send_magic_link("founder@example.com", "https://example.com/claim?token=x")
    assert len(recording.sent) == 1
    assert recording.sent[0]["kind"] == "magic_link"
    assert recording.sent[0]["to"] == "founder@example.com"


def _idea(account_id=None) -> IdeaDocument:
    return IdeaDocument(
        idea_id="idea_notify1", session_id="sess1", account_id=account_id, idea_hash="h",
        raw_text="x", normalized_text="x", share_token="tok_notify",
    )


def _snapshot(deltas: dict) -> SnapshotDocument:
    return SnapshotDocument(
        snapshot_id="snap_notify1", idea_id="idea_notify1", agent_scores={"timing": 8},
        raw_score=70, verdict="go", weights_version=2, trigger="scheduled", deltas=deltas,
    )


async def test_notify_snapshot_suppressed_when_no_delta():
    recording = _RecordingProvider()
    notifications.set_provider(recording)

    idea = _idea(account_id="acct_1")
    snapshot = _snapshot({"raw_score": 0, "dimensions": {"timing": 0}})

    sent = await notifications.notify_snapshot(idea, snapshot)
    assert sent is False
    assert recording.sent == []


async def test_notify_snapshot_suppressed_when_unclaimed(mongo_db):
    recording = _RecordingProvider()
    notifications.set_provider(recording)

    idea = _idea(account_id=None)  # never claimed
    snapshot = _snapshot({"raw_score": 5, "dimensions": {"timing": 5}})

    sent = await notifications.notify_snapshot(idea, snapshot)
    assert sent is False
    assert recording.sent == []


async def test_notify_snapshot_sends_when_delta_and_claimed(mongo_db):
    recording = _RecordingProvider()
    notifications.set_provider(recording)

    await account_repository.create_account(AccountDocument(account_id="acct_1", email="founder@example.com"))
    idea = _idea(account_id="acct_1")
    snapshot = _snapshot({"raw_score": 5, "dimensions": {"timing": 5}})

    sent = await notifications.notify_snapshot(idea, snapshot)
    assert sent is True
    assert len(recording.sent) == 1
    assert recording.sent[0]["to"] == "founder@example.com"
    assert recording.sent[0]["kind"] == "snapshot_digest"
    assert "70/100" in recording.sent[0]["subject"]


async def test_notify_snapshot_version_crossing_noted_in_body(mongo_db):
    recording = _RecordingProvider()
    notifications.set_provider(recording)

    await account_repository.create_account(AccountDocument(account_id="acct_1", email="founder@example.com"))
    idea = _idea(account_id="acct_1")
    snapshot = SnapshotDocument(
        snapshot_id="snap_notify2", idea_id="idea_notify1", agent_scores={"timing": 8},
        raw_score=70, verdict="go", weights_version=3, trigger="scheduled",
        deltas={"raw_score": 5, "dimensions": {"timing": 5}}, version_crossing=True,
    )

    await notifications.notify_snapshot(idea, snapshot)
    assert "weighting changed" in recording.sent[0]["body"]


async def test_criteria_deadline_reminder_suppressed_when_unclaimed(mongo_db):
    import datetime as dt

    recording = _RecordingProvider()
    notifications.set_provider(recording)

    idea = _idea(account_id=None)
    criterion = CriterionDocument(
        criterion_id="crit_notify1", idea_id=idea.idea_id, statement="s", metric="m",
        threshold="t", deadline=dt.datetime.now(dt.timezone.utc),
    )
    sent = await notifications.send_criteria_deadline_reminder(idea, criterion)
    assert sent is False
    assert recording.sent == []


async def test_criteria_deadline_reminder_sent_when_claimed(mongo_db):
    import datetime as dt

    recording = _RecordingProvider()
    notifications.set_provider(recording)

    await account_repository.create_account(AccountDocument(account_id="acct_1", email="founder@example.com"))
    idea = _idea(account_id="acct_1")
    criterion = CriterionDocument(
        criterion_id="crit_notify2", idea_id=idea.idea_id, statement="Ship a demo",
        metric="demo shipped", threshold="yes/no", deadline=dt.datetime.now(dt.timezone.utc),
    )

    sent = await notifications.send_criteria_deadline_reminder(idea, criterion)
    assert sent is True
    assert recording.sent[0]["kind"] == "criteria_deadline"
    assert "Ship a demo" in recording.sent[0]["subject"]
