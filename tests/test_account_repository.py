from models.documents import AccountDocument
from repositories import account_repository as repo


def _make_account(account_id="acct_0000000001", email="founder@example.com") -> AccountDocument:
    return AccountDocument(account_id=account_id, email=email)


async def test_create_and_get_by_email(mongo_db):
    doc = _make_account()
    assert await repo.create_account(doc) is True

    fetched = await repo.get_by_email("founder@example.com")
    assert fetched is not None
    assert fetched.account_id == doc.account_id
    assert fetched.plan == "free"


async def test_get_by_id(mongo_db):
    doc = _make_account()
    await repo.create_account(doc)
    fetched = await repo.get_by_id(doc.account_id)
    assert fetched is not None
    assert fetched.email == "founder@example.com"


async def test_duplicate_email_rejected(mongo_db):
    await repo.create_account(_make_account())
    ok = await repo.create_account(_make_account(account_id="acct_0000000002"))
    assert ok is False


async def test_add_session_id(mongo_db):
    doc = _make_account()
    await repo.create_account(doc)
    assert await repo.add_session_id(doc.account_id, "sess-1") is True

    fetched = await repo.get_by_id(doc.account_id)
    assert "sess-1" in fetched.session_ids


async def test_operations_noop_when_mongo_unavailable(mongo_unavailable):
    assert await repo.create_account(_make_account()) is False
    assert await repo.get_by_email("x@example.com") is None
    assert await repo.get_by_id("acct_x") is None
    assert await repo.add_session_id("acct_x", "s") is False
