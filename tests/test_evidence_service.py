import pytest

from agents.specialist_agents import ALL_AGENTS
from models.documents import AgentResultRecord, ReportDocument
from models.schemas import EvidenceRequest
from orchestrator.state import AgentOutput
from repositories import report_repository
from services import evidence_service, log_service, snapshot_worker


def _patch_agents(monkeypatch, scores: dict[str, int], default=6):
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            score = scores.get(_name, default)
            return AgentOutput(agent=_name, passed=score >= 6, score=score, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


@pytest.fixture(autouse=True)
def _patch_data_layer(monkeypatch):
    async def _fake_gather_signals(keyword):
        return {"keyword": keyword, "signals": {}}

    monkeypatch.setattr(snapshot_worker, "gather_signals", _fake_gather_signals)


async def _seed_idea(session_id="sess1"):
    report = ReportDocument(
        public_id="rep0000001",
        session_id=session_id,
        idea_hash="hash1",
        transcript="Uber for dog walking",
        keyword="dog walking",
        agent_results={
            name: AgentResultRecord(agent=name, passed=True, score=6, evidence="e", feedback="f", model="m")
            for name in ["problem", "solution", "timing", "tam", "moat", "team", "unit_economics", "gtm", "ask", "risk", "yc_signal", "lovers_test"]
        },
        weights_version=2,
        raw_score=60,
        verdict="pivot",
    )
    await report_repository.create_report(report)
    return await log_service.promote_report_to_idea(
        report, session_id=session_id, account_id=None, share_token="tok_ev"
    )


async def test_submit_evidence_triggers_gated_rescore(mongo_db, monkeypatch):
    idea = await _seed_idea()
    _patch_agents(monkeypatch, {"gtm": 9})

    body = EvidenceRequest(type="waitlist", payload={"count": 250})
    result = await evidence_service.submit_evidence(idea, body)
    assert result is not None
    evidence, snapshot = result

    assert evidence.type == "waitlist"
    assert evidence.payload["count"] == 250
    assert evidence.triggered_snapshot_id == snapshot.snapshot_id
    assert snapshot.trigger == "evidence"
    assert snapshot.deltas["dimensions"]["gtm"] == 3
    assert "timing" not in snapshot.deltas["dimensions"]


async def test_submitted_evidence_reaches_agent_context(mongo_db, monkeypatch):
    """Evidence text must reach the agents re-run for it (as transcript
    content, never an agent's own prompt — constraint #7)."""
    idea = await _seed_idea()

    seen_states = []
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            seen_states.append((_name, state.get("transcript", "")))
            return AgentOutput(agent=_name, passed=True, score=7, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)

    body = EvidenceRequest(type="revenue", payload={"mrr": 500})
    await evidence_service.submit_evidence(idea, body)

    gated_transcripts = [t for name, t in seen_states if name == "problem"]
    assert gated_transcripts
    assert '"mrr": 500' in gated_transcripts[0]
