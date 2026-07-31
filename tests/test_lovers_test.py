import json

from agents.lovers_test import lovers_test_agent
from agents.specialist_agents import ALL_AGENTS
from core.config import ANALYSIS_MODEL


def test_registered_in_all_agents():
    assert lovers_test_agent in ALL_AGENTS
    assert lovers_test_agent.name == "lovers_test"


def test_uses_analysis_model():
    assert lovers_test_agent.model == ANALYSIS_MODEL


def test_system_prompt_mentions_reddit_hn_signal_language():
    prompt = lovers_test_agent.system_prompt
    assert "pain_frequency" in prompt or "Reddit" in prompt
    assert "TAM" in prompt  # explicitly contrasted against raw TAM size


async def test_run_parses_valid_response(monkeypatch):
    async def _fake_chat(model, system, user, max_tokens):
        return json.dumps({"score": 9, "evidence": "142 frustrated Reddit posts", "feedback": "Strong love."})

    monkeypatch.setattr("agents.base_agent.chat", _fake_chat)

    state = {
        "transcript": "Uber for dog walking",
        "signals": {"reddit": {"pain_frequency": "high", "post_count": 142}},
    }
    result = await lovers_test_agent.run(state)

    assert result["agent"] == "lovers_test"
    assert result["score"] == 9
    assert result["passed"] is True


async def test_run_degrades_on_malformed_response(monkeypatch):
    async def _fake_chat(model, system, user, max_tokens):
        return "not json"

    monkeypatch.setattr("agents.base_agent.chat", _fake_chat)

    state = {"transcript": "x", "signals": {}}
    result = await lovers_test_agent.run(state)

    assert result["passed"] is False
    assert result["score"] == 0
