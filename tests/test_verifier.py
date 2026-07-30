import json

from agents import verifier
from core.config import REASONING_MODEL
from orchestrator.state import AgentOutput


def _results() -> dict[str, AgentOutput]:
    return {
        "tam": AgentOutput(agent="tam", passed=True, score=9, evidence="Huge market", feedback="Great TAM."),
        "problem": AgentOutput(
            agent="problem", passed=False, score=2, evidence="No one has this problem", feedback="Weak."
        ),
    }


async def test_run_parses_valid_response(monkeypatch):
    async def _fake_chat(model, system, user, max_tokens):
        assert model == REASONING_MODEL
        return json.dumps({
            "confidence_score": 2,
            "conflicts": ["tam claims a huge market while problem finds no one has the problem"],
            "evidence": "tam vs problem disagree on market existence",
            "feedback": "Direct contradiction between tam and problem.",
        })

    monkeypatch.setattr("agents.verifier.chat", _fake_chat)

    result = await verifier.run(_results())

    assert result.agent == "verifier"
    assert result.confidence_score == 2
    assert result.passed is False
    assert len(result.conflicts) == 1


async def test_run_high_confidence_when_no_conflicts(monkeypatch):
    async def _fake_chat(model, system, user, max_tokens):
        return json.dumps({
            "confidence_score": 10,
            "conflicts": [],
            "evidence": "all claims traceable",
            "feedback": "Consistent.",
        })

    monkeypatch.setattr("agents.verifier.chat", _fake_chat)

    result = await verifier.run(_results())
    assert result.confidence_score == 10
    assert result.passed is True
    assert result.conflicts == []


async def test_run_degrades_on_malformed_response(monkeypatch):
    async def _fake_chat(model, system, user, max_tokens):
        return "not json"

    monkeypatch.setattr("agents.verifier.chat", _fake_chat)

    result = await verifier.run(_results())
    assert result.confidence_score == 0
    assert result.passed is False
    assert result.feedback == "Verifier failed to parse response."


async def test_user_message_includes_all_agent_evidence(monkeypatch):
    captured = {}

    async def _fake_chat(model, system, user, max_tokens):
        captured["user"] = user
        return json.dumps({"confidence_score": 8, "evidence": "e", "feedback": "f"})

    monkeypatch.setattr("agents.verifier.chat", _fake_chat)
    await verifier.run(_results())

    assert "Huge market" in captured["user"]
    assert "No one has this problem" in captured["user"]
