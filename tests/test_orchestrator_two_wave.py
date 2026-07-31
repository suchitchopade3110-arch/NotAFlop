import asyncio

import pytest

import agents.verifier as verifier_module
from agents.specialist_agents import ALL_AGENTS
from models.documents import VerifierOutput
from orchestrator import graph
from orchestrator.state import AgentOutput
from repositories import report_repository


def _patch_agents(monkeypatch, score=9):
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name, _score=score):
            return AgentOutput(agent=_name, passed=_score >= 6, score=_score, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


def _patch_verifier(monkeypatch, confidence=0):
    async def _fake_run(results):
        return VerifierOutput(
            confidence_score=confidence, passed=confidence >= 6,
            conflicts=["mocked conflict"], evidence="e", feedback="f", model="m",
        )
    monkeypatch.setattr(verifier_module, "run", _fake_run)


async def _drain(queue: asyncio.Queue) -> list:
    items = []
    while True:
        item = await queue.get()
        if item is None:
            break
        items.append(item)
    return items


async def _drain_background_tasks() -> None:
    pending = list(graph._background_tasks)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


@pytest.fixture(autouse=True)
def _reset_flag(monkeypatch):
    monkeypatch.setattr(graph, "VERIFIER_PENALTY_ENABLED", False)


async def test_shadow_mode_does_not_block_stream_on_verifier(mongo_db, monkeypatch):
    """Default (flag off): final event/score reflect raw_score only —
    the SSE stream must not wait on the Verifier at all."""
    _patch_agents(monkeypatch, score=9)
    _patch_verifier(monkeypatch, confidence=0)  # would heavily penalize if it were blocking

    queue: asyncio.Queue = asyncio.Queue()
    task = graph.spawn_pipeline(
        queue, "Uber for dogs", "dog walking", {}, session_id="shadow-1", ip="1.1.1.1",
    )
    items = await _drain(queue)
    await task

    final = [i for i in items if i["type"] == "final"][0]
    assert final["payload"]["score"] == 90  # raw, unaffected by the (unrun-yet) Verifier

    doc = (await report_repository.list_by_session("shadow-1"))[0]
    assert doc.gating_score == "raw"
    assert doc.verdict == "go"
    assert doc.verifier is None  # hasn't landed yet
    assert doc.adjusted_score is None


async def test_shadow_mode_patches_doc_after_verifier_lands(mongo_db, monkeypatch):
    _patch_agents(monkeypatch, score=9)
    _patch_verifier(monkeypatch, confidence=0)

    queue: asyncio.Queue = asyncio.Queue()
    task = graph.spawn_pipeline(
        queue, "Uber for dogs", "dog walking", {}, session_id="shadow-2", ip="1.1.1.1",
    )
    await _drain(queue)
    await task
    await _drain_background_tasks()  # let the shadow Verifier finish and patch

    doc = (await report_repository.list_by_session("shadow-2"))[0]
    assert doc.verifier is not None
    assert doc.verifier.confidence_score == 0
    assert doc.adjusted_score is not None
    assert doc.adjusted_score < doc.raw_score
    # Gate stays on raw in shadow mode even though it's recorded as a flip
    assert doc.gating_score == "raw"
    assert doc.verdict == "go"


async def test_blocking_mode_gates_on_adjusted_score(mongo_db, monkeypatch):
    monkeypatch.setattr(graph, "VERIFIER_PENALTY_ENABLED", True)
    _patch_agents(monkeypatch, score=9)  # raw_score 90 -> "go"
    _patch_verifier(monkeypatch, confidence=0)  # multiplier 0.7 -> adjusted 63 -> "pivot"

    queue: asyncio.Queue = asyncio.Queue()
    task = graph.spawn_pipeline(
        queue, "Uber for dogs", "dog walking", {}, session_id="blocking-1", ip="1.1.1.1",
    )
    items = await _drain(queue)
    await task

    final = [i for i in items if i["type"] == "final"][0]
    assert final["payload"]["score"] == 63
    assert final["payload"]["verdict"] == "pivot"

    doc = (await report_repository.list_by_session("blocking-1"))[0]
    assert doc.gating_score == "adjusted"
    assert doc.raw_score == 90
    assert doc.adjusted_score == 63
    assert doc.verdict == "pivot"
    assert doc.verdict_would_flip is True
    assert doc.verifier is not None  # included directly, no patch needed


async def test_blocking_mode_falls_back_to_raw_on_verifier_exception(mongo_db, monkeypatch):
    monkeypatch.setattr(graph, "VERIFIER_PENALTY_ENABLED", True)
    _patch_agents(monkeypatch, score=9)

    async def _broken_run(results):
        raise RuntimeError("groq is down")

    monkeypatch.setattr(verifier_module, "run", _broken_run)

    queue: asyncio.Queue = asyncio.Queue()
    task = graph.spawn_pipeline(
        queue, "Uber for dogs", "dog walking", {}, session_id="blocking-2", ip="1.1.1.1",
    )
    items = await _drain(queue)
    await task

    final = [i for i in items if i["type"] == "final"][0]
    assert final["payload"]["score"] == 90  # fell back to raw
    assert any("verifier" in e for e in final["payload"]["errors"])

    doc = (await report_repository.list_by_session("blocking-2"))[0]
    assert doc.gating_score == "raw"
    assert doc.verifier is None
