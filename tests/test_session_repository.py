from repositories import session_repository as repo


async def test_get_or_create_session_creates_new(mongo_db):
    session = await repo.get_or_create_session("sess-abc", ip="9.9.9.9")
    assert session is not None
    assert session.session_id == "sess-abc"
    assert session.ip == "9.9.9.9"
    assert session.report_count == 0


async def test_get_or_create_session_touches_existing(mongo_db):
    first = await repo.get_or_create_session("sess-abc", ip="9.9.9.9")
    second = await repo.get_or_create_session("sess-abc", ip="9.9.9.9")

    assert second.session_id == first.session_id
    assert second.created_at == first.created_at
    assert second.expires_at >= first.expires_at


async def test_increment_report_count(mongo_db):
    await repo.get_or_create_session("sess-xyz", ip=None)
    await repo.increment_report_count("sess-xyz")
    await repo.increment_report_count("sess-xyz")

    session = await repo.get_session("sess-xyz")
    assert session.report_count == 2


async def test_get_session_missing_returns_none(mongo_db):
    assert await repo.get_session("nope") is None


async def test_operations_noop_when_mongo_unavailable(mongo_unavailable):
    assert await repo.get_or_create_session("s", ip=None) is None
    assert await repo.get_session("s") is None
    await repo.increment_report_count("s")  # must not raise
