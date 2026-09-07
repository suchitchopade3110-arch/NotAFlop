"""C3 — per-Groq-call token/cost tracking."""
import logging

import pytest

from core.config import GROQ_PRICE_PER_MILLION_TOKENS
from services import cost_tracking


@pytest.fixture(autouse=True)
def _reset_ledger():
    """The ledger contextvar is process/thread-shared across sync test
    functions (no per-test Task isolation the way async tests get) —
    reset it to its unset default before every test regardless of order."""
    cost_tracking._ledger.set(None)
    yield
    cost_tracking._ledger.set(None)


def test_compute_cost_uses_configured_price_table():
    prices = GROQ_PRICE_PER_MILLION_TOKENS["llama-3.1-8b-instant"]
    cost = cost_tracking.compute_cost_usd("llama-3.1-8b-instant", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost == round(prices["prompt"] + prices["completion"], 8)


def test_compute_cost_zero_tokens_is_zero():
    assert cost_tracking.compute_cost_usd("llama-3.3-70b-versatile", 0, 0) == 0.0


def test_unknown_model_falls_back_to_default_prices():
    from core.config import GROQ_DEFAULT_COMPLETION_PRICE_PER_M, GROQ_DEFAULT_PROMPT_PRICE_PER_M
    cost = cost_tracking.compute_cost_usd("some-future-model", 1_000_000, 1_000_000)
    assert cost == round(GROQ_DEFAULT_PROMPT_PRICE_PER_M + GROQ_DEFAULT_COMPLETION_PRICE_PER_M, 8)


def test_record_call_is_a_noop_without_start_cost_tracking():
    """A chat() call made outside a report run (e.g. Phase 1's filters)
    must not error just because no ledger was started for its context."""
    cost = cost_tracking.record_call("narrow_problem", "m", 100, 50)
    assert cost > 0
    assert cost_tracking.get_ledger() == []


def test_start_cost_tracking_accumulates_calls():
    cost_tracking.start_cost_tracking()
    cost_tracking.record_call("problem", "llama-3.3-70b-versatile", 500, 200)
    cost_tracking.record_call("solution", "llama-3.3-70b-versatile", 400, 150)

    ledger = cost_tracking.get_ledger()
    assert len(ledger) == 2
    assert ledger[0]["agent"] == "problem"
    assert ledger[1]["agent"] == "solution"

    total = cost_tracking.get_total_cost_usd()
    assert total == round(sum(e["cost_usd"] for e in ledger), 8)
    assert total > 0


def test_cost_since_isolates_calls_after_a_marker():
    cost_tracking.start_cost_tracking()
    cost_tracking.record_call("problem", "llama-3.3-70b-versatile", 500, 200)
    marker = len(cost_tracking.get_ledger())
    cost_tracking.record_call("verifier", "llama-3.3-70b-versatile", 300, 100)

    verifier_only_cost = cost_tracking.cost_since(marker)
    full_total = cost_tracking.get_total_cost_usd()
    assert 0 < verifier_only_cost < full_total


async def test_groq_client_records_cost_and_logs_it(monkeypatch, caplog):
    """Integration with services.groq_client.chat()."""
    from services import groq_client

    class _FakeResponse:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 40},
            }

    class _FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return _FakeResponse()

    monkeypatch.setattr(groq_client.httpx, "AsyncClient", _FakeAsyncClient)

    cost_tracking.start_cost_tracking()
    caplog.set_level(logging.INFO, logger="notaflop.groq_client")

    result = await groq_client.chat("llama-3.3-70b-versatile", "sys", "user", agent_name="problem")

    assert result == "hello"
    ledger = cost_tracking.get_ledger()
    assert len(ledger) == 1
    assert ledger[0]["agent"] == "problem"
    assert ledger[0]["prompt_tokens"] == 120
    assert ledger[0]["completion_tokens"] == 40
    assert ledger[0]["cost_usd"] > 0

    assert "groq_call_cost" in caplog.text
    assert "agent=problem" in caplog.text
    assert "prompt_tokens=120" in caplog.text
    assert "completion_tokens=40" in caplog.text
