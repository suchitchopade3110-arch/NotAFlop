from fastapi import FastAPI
from fastapi.testclient import TestClient

from models.documents import AgentResultRecord, ReportDocument
from repositories import report_repository as repo
from routers import reports

app = FastAPI()
app.include_router(reports.router, prefix="/api")
client = TestClient(app)


def _make_report(public_id="abc1234567", session_id="sess1") -> ReportDocument:
    return ReportDocument(
        public_id=public_id,
        session_id=session_id,
        ip="1.2.3.4",
        idea_hash="hash1",
        transcript="Uber for dog walking",
        keyword="dog walking",
        signals={"reddit": {"post_count": 10}},
        agent_results={
            "problem": AgentResultRecord(
                agent="problem", passed=True, score=8, evidence="e", feedback="f", model="m"
            )
        },
        weights_version=1,
        raw_score=80,
        verdict="go",
    )


async def test_get_report_success(mongo_db):
    doc = _make_report()
    await repo.create_report(doc)

    res = client.get(f"/api/reports/{doc.public_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["public_id"] == doc.public_id
    assert body["raw_score"] == 80
    assert "ip" not in body
    assert "session_id" not in body


async def test_get_report_not_found(mongo_db):
    res = client.get("/api/reports/does-not-exist")
    assert res.status_code == 404


async def test_list_session_reports(mongo_db):
    doc1 = _make_report(public_id="pid0000001", session_id="s1")
    doc2 = _make_report(public_id="pid0000002", session_id="s1")
    other = _make_report(public_id="pid0000003", session_id="s2")
    await repo.create_report(doc1)
    await repo.create_report(doc2)
    await repo.create_report(other)

    res = client.get("/api/sessions/s1/reports")
    assert res.status_code == 200
    body = res.json()
    assert {r["public_id"] for r in body} == {"pid0000001", "pid0000002"}
    assert "agent_results" not in body[0]


async def test_list_session_reports_empty(mongo_db):
    res = client.get("/api/sessions/nobody/reports")
    assert res.status_code == 200
    assert res.json() == []
