import asyncio

from agents.specialist_agents import ALL_AGENTS
from orchestrator import graph
from orchestrator.state import AgentOutput
from repositories import report_repository


def _patch_agents(monkeypatch, score=8):
    """Replace every real agent's .run with a fast, deterministic fake so
    tests don't hit Groq."""
    for agent in ALL_AGENTS:
        async def _run(state, _name=agent.name, _score=score):
            return AgentOutput(agent=_name, passed=_score >= 6, score=_score, evidence="e", feedback="f")
        monkeypatch.setattr(agent, "run", _run)


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

    final_events = [i for i in items if i["type"] == "final"]
    assert len(final_events) == 1
    assert final_events[0]["payload"]["score"] > 0
    assert len([i for i in items if i["type"] == "agent"]) == len(ALL_AGENTS)

    docs = await report_repository.list_by_session("sess-1")
    assert len(docs) == 1
    doc = docs[0]
    assert doc.raw_score == final_events[0]["payload"]["score"]
    assert doc.verdict == final_events[0]["payload"]["verdict"]
    assert doc.weights_version == graph.WEIGHTS_VERSION
    assert set(doc.agent_results.keys()) == {a.name for a in ALL_AGENTS}
    assert doc.agent_results["problem"].model == graph._AGENT_MODEL_BY_NAME["problem"]
    assert doc.tier_reached == 2  # score 8/10 across the board clears PIVOT_THRESHOLD


async def test_no_persist_without_session_id(mongo_db, monkeypatch):
    _patch_agents(monkeypatch)

    queue: asyncio.Queue = asyncio.Queue()
    task = graph.spawn_pipeline(queue, "x", "y", {}, session_id=None, ip=None)
    await _drain(queue)
    await task

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

    # Whatever's still pending must be allowed to finish — this is what a
    # real ASGI server does implicitly by not killing the process.
    pending = [t for t in graph._background_tasks]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    docs = await report_repository.list_by_session("sess-disconnect")
    assert len(docs) == 1
