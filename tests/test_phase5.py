from fastapi.testclient import TestClient
from main import app
from models.documents import ReportDocument, AgentResultRecord


def _make_dummy_doc(public_id: str, tier_reached: int) -> ReportDocument:
    return ReportDocument(
        public_id=public_id,
        session_id="test_session",
        idea_hash="hash123",
        transcript="We build an AI dev tool for code reviews.",
        keyword="AI code review",
        agent_results={
            "gtm": AgentResultRecord(
                agent="gtm", passed=False, score=2, evidence="ev", feedback="Weak channel", model="m"
            )
        },
        weights_version=2,
        raw_score=60 if tier_reached >= 2 else 35,
        verdict="go" if tier_reached >= 2 else "no-go",
        tier_reached=tier_reached,
    )


def test_phase5_allowed_when_tier_reached_is_2(monkeypatch):
    client = TestClient(app)
    doc = _make_dummy_doc("rep_allowed", tier_reached=2)

    async def _fake_get(public_id):
        assert public_id == "rep_allowed"
        return doc

    monkeypatch.setattr("repositories.report_repository.get_by_public_id", _fake_get)

    res = client.post("/api/phase5/plan", json={"report_id": "rep_allowed"})
    assert res.status_code == 200
    data = res.json()
    assert "roadmap" in data
    assert "team" in data
    assert len(data["roadmap"]) == 3


def test_phase5_locked_403_when_tier_reached_below_2(monkeypatch):
    client = TestClient(app)
    doc = _make_dummy_doc("rep_locked", tier_reached=1)

    async def _fake_get(public_id):
        assert public_id == "rep_locked"
        return doc

    monkeypatch.setattr("repositories.report_repository.get_by_public_id", _fake_get)

    res = client.post("/api/phase5/plan", json={"report_id": "rep_locked"})
    assert res.status_code == 403
    assert res.json()["detail"] == "Phase 5 roadmap is locked for ideas scoring below 50 in Phase 4 gate."


def test_phase5_returns_404_when_report_not_found(monkeypatch):
    client = TestClient(app)

    async def _fake_get(public_id):
        return None

    monkeypatch.setattr("repositories.report_repository.get_by_public_id", _fake_get)

    res = client.post("/api/phase5/plan", json={"report_id": "rep_nonexistent"})
    assert res.status_code == 404
    assert res.json()["detail"] == "Report not found."
