"""A2 — GET /internal/verifier/stats: repository-level aggregation and the
admin-gated router."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import config as core_config
from core import dependencies
from models.documents import AgentResultRecord, ReportDocument, VerifierOutput
from repositories import report_repository as repo
from routers import internal


def _make_report(public_id, raw_score, adjusted_score=None, with_verifier=True) -> ReportDocument:
    return ReportDocument(
        public_id=public_id,
        session_id="sess1",
        ip="1.2.3.4",
        idea_hash=f"hash-{public_id}",
        transcript="Uber for dog walking",
        keyword="dog walking",
        agent_results={
            "problem": AgentResultRecord(agent="problem", passed=True, score=8, evidence="e", feedback="f", model="m")
        },
        verifier=(
            VerifierOutput(confidence_score=7, passed=True, evidence="e", feedback="f", model="m")
            if with_verifier
            else None
        ),
        weights_version=2,
        raw_score=raw_score,
        adjusted_score=adjusted_score,
        verdict="go",
    )


# ── Repository ────────────────────────────────────────────────

async def test_stats_empty_when_no_reports(mongo_db):
    stats = await repo.get_verifier_divergence_stats()
    assert stats["count"] == 0
    assert stats["mean_absolute_delta"] == 0.0
    assert stats["max_delta"] == 0
    assert stats["distribution"] == {"0": 0, "1-5": 0, "6-10": 0, "11-20": 0, "21+": 0}


async def test_stats_ignores_reports_without_verifier(mongo_db):
    await repo.create_report(_make_report("pid0000001", raw_score=80, adjusted_score=80, with_verifier=False))
    stats = await repo.get_verifier_divergence_stats()
    assert stats["count"] == 0


async def test_stats_ignores_reports_verifier_not_yet_landed(mongo_db):
    """Shadow mode: the report can be persisted before the fire-and-forget
    Verifier patch lands — adjusted_score is still None at that point."""
    await repo.create_report(_make_report("pid0000002", raw_score=80, adjusted_score=None, with_verifier=False))
    stats = await repo.get_verifier_divergence_stats()
    assert stats["count"] == 0


async def test_stats_computes_count_mean_and_max(mongo_db):
    await repo.create_report(_make_report("pid0000003", raw_score=80, adjusted_score=80))   # delta 0
    await repo.create_report(_make_report("pid0000004", raw_score=80, adjusted_score=72))   # delta 8
    await repo.create_report(_make_report("pid0000005", raw_score=90, adjusted_score=63))   # delta 27

    stats = await repo.get_verifier_divergence_stats()
    assert stats["count"] == 3
    assert stats["max_delta"] == 27
    assert stats["mean_absolute_delta"] == round((0 + 8 + 27) / 3, 2)


async def test_stats_distribution_buckets(mongo_db):
    await repo.create_report(_make_report("pid0000006", raw_score=80, adjusted_score=80))   # 0
    await repo.create_report(_make_report("pid0000007", raw_score=80, adjusted_score=76))   # 4  -> 1-5
    await repo.create_report(_make_report("pid0000008", raw_score=80, adjusted_score=71))   # 9  -> 6-10
    await repo.create_report(_make_report("pid0000009", raw_score=80, adjusted_score=65))   # 15 -> 11-20
    await repo.create_report(_make_report("pid0000010", raw_score=90, adjusted_score=60))   # 30 -> 21+

    stats = await repo.get_verifier_divergence_stats()
    assert stats["distribution"] == {"0": 1, "1-5": 1, "6-10": 1, "11-20": 1, "21+": 1}


async def test_stats_noop_when_mongo_unavailable(mongo_unavailable):
    stats = await repo.get_verifier_divergence_stats()
    assert stats["count"] == 0


# ── Admin-gated router ───────────────────────────────────────

app = FastAPI()
app.include_router(internal.router, prefix="/internal")
client = TestClient(app)


def test_stats_endpoint_503_when_admin_key_unconfigured(monkeypatch, mongo_db):
    monkeypatch.setattr(core_config, "ADMIN_API_KEY", "")
    monkeypatch.setattr(dependencies, "ADMIN_API_KEY", "")
    res = client.get("/internal/verifier/stats")
    assert res.status_code == 503


def test_stats_endpoint_401_when_key_missing_or_wrong(monkeypatch, mongo_db):
    monkeypatch.setattr(dependencies, "ADMIN_API_KEY", "secret-key")
    res = client.get("/internal/verifier/stats")
    assert res.status_code == 401

    res = client.get("/internal/verifier/stats", headers={"X-Admin-Key": "wrong"})
    assert res.status_code == 401


def test_stats_endpoint_200_with_correct_key(monkeypatch, mongo_db):
    monkeypatch.setattr(dependencies, "ADMIN_API_KEY", "secret-key")
    res = client.get("/internal/verifier/stats", headers={"X-Admin-Key": "secret-key"})
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 0
    assert "distribution" in body
