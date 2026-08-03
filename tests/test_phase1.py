import json

from agents import narrow_problem, pitch_clarity
from core.config import FILTER_MODEL


async def test_narrow_problem_pins_temperature_zero(monkeypatch):
    captured = {}

    async def _fake_chat(model, system, user, max_tokens, temperature=None):
        captured["temperature"] = temperature
        return json.dumps({"passed": True, "score": 8, "feedback": "Specific enough."})

    monkeypatch.setattr("agents.narrow_problem.chat", _fake_chat)
    await narrow_problem.run("Freelance designers spend 3 hours invoicing per client.")

    assert captured["temperature"] == 0


async def test_pitch_clarity_pins_temperature_zero(monkeypatch):
    captured = {}

    async def _fake_chat(model, system, user, max_tokens, temperature=None):
        captured["temperature"] = temperature
        return json.dumps({"passed": True, "score": 8, "feedback": "Clear pitch."})

    monkeypatch.setattr("agents.pitch_clarity.chat", _fake_chat)
    await pitch_clarity.run("We help freelance designers invoice clients faster.")

    assert captured["temperature"] == 0


async def test_groq_client_omits_temperature_by_default(monkeypatch):
    """Every other agent (Phase 3 specialists, Verifier, keyword extractor)
    calls chat() without temperature — this must stay opt-in, not become
    a global default, or Phase 1's scoped fix silently spreads."""
    captured = {}

    class _FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            captured["payload"] = json
            return _FakeResponse()

    monkeypatch.setattr("services.groq_client.httpx.AsyncClient", _FakeAsyncClient)

    from services.groq_client import chat

    await chat(FILTER_MODEL, "system", "user", 300)
    assert "temperature" not in captured["payload"]

    await chat(FILTER_MODEL, "system", "user", 300, temperature=0)
    assert captured["payload"]["temperature"] == 0
