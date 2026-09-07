import asyncio

import pytest

import agents.verifier as verifier_module
from agents.specialist_agents import ALL_AGENTS
from models.documents import VerifierOutput
from orchestrator import graph
from orchestrator.state import AgentOutput
from repositories import report_repository
from services import cost_tracking


def _patch_agents(monkeypatch, score=8):
    """Replace every real agent's .run with a fast, deterministic fake so
    tests don't hit Groq."""
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name, _score=score):
            return AgentOutput(agent=_name, passed=_score >= 6, score=_score, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


@pytest.fixture(autouse=True)
def _patch_verifier(monkeypatch):
    """Shadow mode spawns the Verifier after every persisted report — these
    tests are about the persistence guarantee, not the Verifier itself, so
    fake it out to avoid a real Groq call."""
    async def _fake_run(results):
        return VerifierOutput(confidence_score=9, passed=True, evidence="e", feedback="f", model="m")
    monkeypatch.setattr(verifier_module, "run", _fake_run)


async def _drain_background_tasks() -> None:
    """Waits out any fire-and-forget tasks (e.g. the shadow Verifier) so a
    test doesn't leave orphaned tasks behind for the next one."""
    pending = list(graph._background_tasks)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def _drain(queue: asyncio.Queue) -> list:
    items = []
    while True:
        item = await queue.get()
        if item is None:
            break
        items.append(item)
    return items


async def test_spawn_pipeline_streams_and_persists(mongo_db, monkeypatch):
    _patch_agents(monkeypatch, score=8)

    queue: asyncio.Queue = asyncio.Queue()
    task = graph.spawn_pipeline(
        queue, "Uber for dogs", "dog walking", {"reddit": {"post_count": 5}},
        session_id="sess-1", ip="1.2.3.4",
    )

    items = await _drain(queue)
    await task  # pipeline (incl. persistence) is fully finished by now
    await _drain_background_tasks()  # let the shadow Verifier finish too

    final_events = [i for i in items if i["type"] == "final"]
    assert len(final_events) == 1
    assert final_events[0]["payload"]["score"] > 0
    assert len([i for i in items if i["type"] == "agent"]) == len(ALL_AGENTS)

    # B3: signal_quality streams first, ahead of any agent event — one
    # reddit source present -> low_confidence (< 2 live sources).
    assert items[0]["type"] == "signal_quality"
    assert items[0]["payload"]["low_confidence"] is True
    assert items[0]["payload"]["signal_quality_by_source"]["reddit"] > 0

    docs = await report_repository.list_by_session("sess-1")
    assert len(docs) == 1
    doc = docs[0]
    assert doc.public_id == final_events[0]["payload"]["public_id"]
    assert doc.raw_score == final_events[0]["payload"]["score"]
    assert doc.verdict == final_events[0]["payload"]["verdict"]
    assert doc.weights_version == graph.WEIGHTS_VERSION
    assert set(doc.agent_results.keys()) == {a.name for a in ALL_AGENTS}
    assert doc.agent_results["problem"].model == graph._AGENT_MODEL_BY_NAME["problem"]
    assert doc.tier_reached == 2  # score 8/10 across the board clears PIVOT_THRESHOLD
    assert doc.low_confidence is True
    assert doc.signal_quality > 0
    assert doc.signal_quality_by_source["reddit"] > 0
    # B4: single-source signals here -> nothing to cross-check for conflicts.
    assert doc.conflicts == []
    assert items[0]["payload"]["conflicts"] == []


async def test_conflicting_signals_are_streamed_and_persisted(mongo_db, monkeypatch):
    """B4: a real cross-source conflict in the signals passed to /analyze
    shows up in the signal_quality SSE event and on the persisted doc."""
    _patch_agents(monkeypatch, score=8)

    conflicting_signals = {
        "google_trends": {"trend": "declining", "raw": [80, 60, 40]},
        "reddit": {"pain_frequency": "high", "post_count": 50},
    }

    queue: asyncio.Queue = asyncio.Queue()
    task = graph.spawn_pipeline(
        queue, "Uber for dogs", "dog walking", conflicting_signals,
        session_id="sess-conflict", ip="1.2.3.4",
    )
    items = await _drain(queue)
    await task
    await _drain_background_tasks()

    assert items[0]["type"] == "signal_quality"
    assert len(items[0]["payload"]["conflicts"]) == 1
    assert items[0]["payload"]["conflicts"][0]["dimension"] == "interest_vs_pain"

    doc = (await report_repository.list_by_session("sess-conflict"))[0]
    assert len(doc.conflicts) == 1
    assert doc.conflicts[0]["dimension"] == "interest_vs_pain"


async def test_report_cost_usd_persisted_and_topped_up_after_shadow_verifier(mongo_db, monkeypatch):
    """C3: each agent's simulated Groq call records a cost into the run's
    ledger; the report is persisted with the wave-1 total, then the
    shadow Verifier's own cost is $inc'd on afterward (it runs in a
    separate task spawned after that initial total was already read)."""
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name):
            cost_tracking.record_call(_name, "m", 100, 50)
            return AgentOutput(agent=_name, passed=True, score=8, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)

    async def _fake_verifier_run(results):
        cost_tracking.record_call("verifier", "m", 200, 80)
        return VerifierOutput(confidence_score=9, passed=True, evidence="e", feedback="f", model="m")
    monkeypatch.setattr(verifier_module, "run", _fake_verifier_run)

    queue: asyncio.Queue = asyncio.Queue()
    task = graph.spawn_pipeline(
        queue, "Uber for dogs", "dog walking", {}, session_id="sess-cost", ip="1.2.3.4",
    )
    await _drain(queue)
    await task

    # Persisted immediately after wave 1 -> only the 12 agents' cost, not
    # the shadow Verifier's (hasn't run yet).
    doc = (await report_repository.list_by_session("sess-cost"))[0]
    agents_only_cost = doc.report_cost_usd
    assert agents_only_cost > 0

    await _drain_background_tasks()  # let the shadow Verifier finish and patch

    doc = (await report_repository.list_by_session("sess-cost"))[0]
    assert doc.report_cost_usd > agents_only_cost  # verifier's cost added on top
    expected_verifier_cost = cost_tracking.compute_cost_usd("m", 200, 80)
    assert round(doc.report_cost_usd - agents_only_cost, 8) == expected_verifier_cost


async def test_no_persist_without_session_id(mongo_db, monkeypatch):
    _patch_agents(monkeypatch)

    queue: asyncio.Queue = asyncio.Queue()
    task = graph.spawn_pipeline(queue, "x", "y", {}, session_id=None, ip=None)
    await _drain(queue)
    await task
    await _drain_background_tasks()

    coll = mongo_db["reports"]
    assert await coll.count_documents({}) == 0


async def test_persists_even_if_sse_consumer_disconnects_early(mongo_db, monkeypatch):
    """The whole point of the independent-task design: closing the SSE
    generator after reading only one event must not stop the save."""
    _patch_agents(monkeypatch)

    gen = graph.stream_analysis(
        "Uber for dogs", "dog walking", {}, session_id="sess-disconnect", ip="9.9.9.9",
    )

    first = await gen.__anext__()  # advances the generator, spawns the background task
    assert first.startswith("data: ")

    await gen.aclose()  # simulates the client disconnecting mid-stream

    # Whatever's still pending (the pipeline, then the shadow Verifier it
    # spawns) must be allowed to finish — this is what a real ASGI server
    # does implicitly by not killing the process.
    await _drain_background_tasks()
    await _drain_background_tasks()  # the pipeline's own finally spawns the shadow task after the first drain

    docs = await report_repository.list_by_session("sess-disconnect")
    assert len(docs) == 1
