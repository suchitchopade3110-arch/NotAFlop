"""
Shared test fixtures. No live services in tests — Mongo is mocked with
mongomock-motor, Redis with fakeredis.
"""
import fakeredis.aioredis
import pytest
from mongomock_motor import AsyncMongoMockClient

from services import mongo as mongo_service


@pytest.fixture
def mongo_db(monkeypatch):
    """Patches services.mongo's module-level db handle with an in-memory
    mongomock database, marks Mongo 'available', and restores state after."""
    client = AsyncMongoMockClient()
    db = client["notaflop_test"]

    monkeypatch.setattr(mongo_service, "_client", client)
    monkeypatch.setattr(mongo_service, "_db", db)
    monkeypatch.setattr(mongo_service, "_mongo_available", True)

    yield db


@pytest.fixture
def mongo_unavailable(monkeypatch):
    """Simulates Mongo being down: get_db() returns None."""
    monkeypatch.setattr(mongo_service, "_client", None)
    monkeypatch.setattr(mongo_service, "_db", None)
    monkeypatch.setattr(mongo_service, "_mongo_available", False)


@pytest.fixture
def fake_redis():
    """A fresh in-memory async Redis instance per test."""
    server = fakeredis.aioredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    yield client
