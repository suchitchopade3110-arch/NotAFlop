import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import agents.verifier as verifier_module
from agents.specialist_agents import ALL_AGENTS
from models.documents import VerifierOutput
from orchestrator.state import AgentOutput
from routers import phase3
from services import rate_limiter

app = FastAPI()
app.include_router(phase3.router, prefix="/api/phase3")
client = TestClient(app)


@pytest.fixture(autouse=True)
def _patch_agents(monkeypatch):
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            return AgentOutput(agent=_name, passed=True, score=8, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


@pytest.fixture(autouse=True)
def _patch_verifier(monkeypatch):
    async def _fake_run(results):
        return VerifierOutput(confidence_score=9, passed=True, evidence="e", feedback="f", model="m")
        monkeypatch.setattr(verifier_module, "run", _fake_run)


@pytest.fixture(autouse=True)
def _reset_rate_limiter_state(monkeypatch, fake_redis):
    monkeypatch.setattr(rate_limiter, "_redis_available", True)
    monkeypatch.setattr(rate_limiter, "_memory_store", {})

    async def _fake_get_client():
        return fake_redis

    monkeypatch.setattr(rate_limiter, "get_client", _fake_get_client)


def test_phase3_blocks_pitch_with_failed_filter_result(mongo_db):
    payload = {
        "transcript": "SIDDAI pitch transcript text here",
        "keyword": "AI assistant",
        "signals": {},
        "filter_result": {
            "verdict": "fail",
            "feedback": "clarity or problem specificity too weak"
        }
    }
    res = client.post("/api/phase3/analyze", json=payload)
    assert res.status_code == 422
    assert "This pitch didn't pass Phase 1 filtering" in res.json()["detail"]
    assert "clarity or problem specificity too weak" in res.json()["detail"]


def test_phase3_allows_pitch_with_passed_filter_result(mongo_db):
    payload = {
        "transcript": "Valid pitch transcript",
        "keyword": "SaaS platform",
        "signals": {},
        "filter_result": {
            "verdict": "pass",
            "feedback": "Pitch is clear and specific."
        }
    }
    res = client.post("/api/phase3/analyze", json=payload)
    assert res.status_code == 200


def test_phase3_allows_pitch_without_filter_result(mongo_db):
    payload = {
        "transcript": "Direct API test pitch transcript",
        "keyword": "Direct API",
        "signals": {}
    }
    res = client.post("/api/phase3/analyze", json=payload)
    assert res.status_code == 200
