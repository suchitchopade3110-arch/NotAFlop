from services import mongo


async def test_connect_failure_degrades_gracefully(monkeypatch):
    """An unreachable Mongo must not raise — it should flip _mongo_available
    to False and leave get_db() returning None."""

    class _ExplodingClient:
        def __init__(self, *a, **kw):
            self.admin = self

        async def command(self, *a, **kw):
            raise ConnectionError("no mongo here")

        def close(self):
            pass

    monkeypatch.setattr(mongo, "AsyncIOMotorClient", _ExplodingClient)

    await mongo.connect()

    assert mongo.is_available() is False
    assert mongo.get_db() is None

    await mongo.disconnect()


async def test_get_db_returns_none_when_marked_unavailable(mongo_unavailable):
    assert mongo.get_db() is None
    assert mongo.is_available() is False


async def test_mongo_db_fixture_is_available(mongo_db):
    assert mongo.is_available() is True
    assert mongo.get_db() is mongo_db


def test_mark_unavailable_flips_flag(mongo_db):
    assert mongo.is_available() is True
    mongo.mark_unavailable(RuntimeError("boom"))
    assert mongo.is_available() is False
    assert mongo.get_db() is None
