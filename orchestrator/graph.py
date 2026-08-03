"""
LangGraph orchestrator for Phase 3 - Analyze.
Spawns the 12 specialist agents in parallel via a single fan-out node
(wave 1). Results stream back via an async generator consumed by the
SSE endpoint.

Persistence guarantee: running the agents, aggregating, and saving the
report happens in `_run_pipeline`, scheduled as its own independent
asyncio.Task (see `spawn_pipeline`) rather than being driven by the SSE
generator's own control flow. If the SSE client disconnects mid-stream,
Starlette stops consuming `stream_analysis`'s generator, but that does
not cancel or garbage-collect the pipeline task — it's anchored in
`_background_tasks` and keeps running to completion, including the
persistence call in its `finally` block.

Verifier (wave 2) is a meta-agent that audits wave 1's outputs, gated
by core.config.VERIFIER_PENALTY_ENABLED:
  - False (default, shadow mode): NOT on the critical path. The SSE
    stream finishes and the report is persisted on raw_score exactly as
    before, then the Verifier runs fire-and-forget (_spawn_verifier_shadow)
    and patches the persisted doc with verifier/adjusted_score once done.
  - True: blocking. Wave 2 runs before the SSE 'final' event, and the
    gate uses adjusted_score instead of raw_score.
Flipping the flag flips both behaviors together — there's no
independent "blocking but still gate on raw" combination.
"""
import asyncio
import json
import logging
import time
from typing import AsyncGenerator, Literal

try:
    from langgraph.graph import END, StateGraph
except ModuleNotFoundError:
    END = None
    StateGraph = None

from agents import verifier as verifier_agent
from agents.specialist_agents import ALL_AGENTS
from core.config import VERIFIER_PENALTY_ENABLED, WEIGHTS_VERSION
from core.ids import generate_public_id
from models.documents import AgentResultRecord, ReportDocument, VerifierOutput
from orchestrator.state import AgentOutput, GraphState
from repositories import report_repository, session_repository
from services.gate import PIVOT_THRESHOLD, aggregate_results, apply_verifier_penalty

logger = logging.getLogger("notaflop.orchestrator")

_AGENT_MODEL_BY_NAME = {agent.name: agent.model for agent in ALL_AGENTS}

# Anchors pipeline tasks so they aren't garbage-collected once the SSE
# generator that spawned them stops being referenced (e.g. on disconnect).
_background_tasks: set[asyncio.Task] = set()


async def run_agents_node(state: GraphState) -> GraphState:
    """Fan-out: run all 11 agents in parallel, collect results."""
    tasks = [agent.run(state) for agent in ALL_AGENTS]
    outputs: list[AgentOutput] = await asyncio.gather(*tasks, return_exceptions=True)

    results = {}
    errors = list(state.get("errors", []))

    for agent, output in zip(ALL_AGENTS, outputs):
        if isinstance(output, Exception):
            errors.append(f"{agent.name}: {str(output)}")
            results[agent.name] = AgentOutput(
                agent=agent.name,
                passed=False,
                score=0,
                evidence="",
                feedback="Agent error.",
            )
        else:
            results[agent.name] = output

    return {**state, "results": results, "errors": errors}


async def aggregate_node(state: GraphState) -> GraphState:
    """Compute VC-weighted score and emit verdict."""
    score, verdict = aggregate_results(state.get("results", {}))
    return {**state, "aggregated_score": score, "verdict": verdict}


def build_graph():
    if StateGraph is None:
        raise RuntimeError("langgraph is not installed. Install requirements.txt to use build_graph().")

    graph = StateGraph(GraphState)
    graph.add_node("run_agents", run_agents_node)
    graph.add_node("aggregate", aggregate_node)
    graph.set_entry_point("run_agents")
    graph.add_edge("run_agents", "aggregate")
    graph.add_edge("aggregate", END)
    return graph.compile()


_graph = build_graph() if StateGraph is not None else None


async def _persist_report(
    transcript: str,
    keyword: str,
    signals: dict,
    results: dict[str, AgentOutput],
    raw_score: int,
    verdict: str,
    session_id: str | None,
    ip: str | None,
    filter_result: dict | None,
    *,
    public_id: str | None = None,
    verifier: VerifierOutput | None = None,
    adjusted_score: int | None = None,
    gating_score: Literal["raw", "adjusted"] = "raw",
    verdict_would_flip: bool = False,
) -> str | None:
    """Returns the new report's public_id if it was saved, else None —
    shadow mode needs the id back to patch the Verifier result in later."""
    if not session_id:
        logger.warning("No session_id supplied — report not persisted.")
        return None

    agent_results = {
        name: AgentResultRecord(
            agent=out["agent"],
            passed=out["passed"],
            score=out["score"],
            evidence=out["evidence"],
            feedback=out["feedback"],
            model=_AGENT_MODEL_BY_NAME.get(name, "unknown"),
        )
        for name, out in results.items()
    }

    if not public_id:
        public_id = generate_public_id()
    doc = ReportDocument(
        public_id=public_id,
        session_id=session_id,
        ip=ip,
        idea_hash=report_repository.compute_idea_hash(transcript),
        transcript=transcript,
        keyword=keyword,
        signals=signals,
        filter_result=filter_result,
        agent_results=agent_results,
        verifier=verifier,
        weights_version=WEIGHTS_VERSION,
        raw_score=raw_score,
        adjusted_score=adjusted_score,
        verdict=verdict,
        gating_score=gating_score,
        verdict_would_flip=verdict_would_flip,
        tier_reached=2 if raw_score >= PIVOT_THRESHOLD else 1,
    )

    saved = await report_repository.create_report(doc)
    if not saved:
        return None

    await session_repository.increment_report_count(session_id)
    return public_id


async def _run_verifier_shadow(public_id: str, raw_score: int, results: dict[str, AgentOutput]) -> None:
    """Fire-and-forget: runs the Verifier after the report already
    streamed and was persisted on raw_score, then patches the doc. Never
    on the SSE critical path while VERIFIER_PENALTY_ENABLED is false."""
    wave2_started_at = time.monotonic()
    verifier_output = await verifier_agent.run(results)
    logger.info("wave2_complete elapsed_s=%.2f blocking=False", time.monotonic() - wave2_started_at)

    adjusted_score, _adjusted_verdict, verdict_would_flip = apply_verifier_penalty(raw_score, verifier_output)
    await report_repository.patch_verifier(public_id, verifier_output, adjusted_score, verdict_would_flip)


def _spawn_verifier_shadow(public_id: str, raw_score: int, results: dict[str, AgentOutput]) -> asyncio.Task:
    task = asyncio.create_task(_run_verifier_shadow(public_id, raw_score, results))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def _run_pipeline(
    queue: "asyncio.Queue[dict | None]",
    transcript: str,
    keyword: str,
    signals: dict,
    session_id: str | None,
    ip: str | None,
    filter_result: dict | None,
) -> None:
    """Runs all agents, streams progress onto `queue`, aggregates, and
    persists — regardless of whether anything is still reading `queue`."""
    initial_state: GraphState = {
        "transcript": transcript,
        "keyword": keyword,
        "signals": signals,
        "results": {},
        "aggregated_score": None,
        "verdict": None,
        "errors": [],
    }

    tasks = {agent.name: asyncio.create_task(agent.run(initial_state)) for agent in ALL_AGENTS}
    results: dict[str, AgentOutput] = {}
    errors: list[str] = []
    pending = dict(tasks)

    raw_score = 0
    verdict = "no-go"
    gated_score = 0
    gated_verdict = "no-go"
    gating_score: Literal["raw", "adjusted"] = "raw"
    verifier_output: VerifierOutput | None = None
    adjusted_score: int | None = None
    verdict_would_flip = False
    wave1_started_at = time.monotonic()

    try:
        while pending:
            done, _ = await asyncio.wait(list(pending.values()), return_when=asyncio.FIRST_COMPLETED)
            for fut in done:
                for name, task in list(pending.items()):
                    if task is fut:
                        try:
                            result: AgentOutput = await task
                            results[name] = result
                            await queue.put({"type": "agent", "payload": result})
                        except Exception as exc:
                            errors.append(f"{name}: {str(exc)}")
                            await queue.put(
                                {"type": "agent_error", "payload": {"agent": name, "error": str(exc)}}
                            )
                        del pending[name]
                        break

        raw_score, verdict = aggregate_results(results)
        gated_score, gated_verdict = raw_score, verdict
        logger.info("wave1_complete elapsed_s=%.2f", time.monotonic() - wave1_started_at)

        if VERIFIER_PENALTY_ENABLED:
            # Blocking wave 2 — Verifier is on the critical path, and the
            # gate uses adjusted_score while this flag is on.
            try:
                wave2_started_at = time.monotonic()
                verifier_output = await verifier_agent.run(results)
                logger.info(
                    "wave2_complete elapsed_s=%.2f blocking=True",
                    time.monotonic() - wave2_started_at,
                )
                adjusted_score, gated_verdict, verdict_would_flip = apply_verifier_penalty(
                    raw_score, verifier_output
                )
                gated_score = adjusted_score
                gating_score = "adjusted"
            except Exception:
                errors.append("verifier: blocking call failed — gated on raw_score instead.")
                logger.error("Blocking Verifier call failed — falling back to raw_score.", exc_info=True)

        public_id = generate_public_id() if session_id else None
        await queue.put(
            {
                "type": "final",
                "payload": {
                    "public_id": public_id,
                    "score": gated_score,
                    "verdict": gated_verdict,
                    "errors": errors,
                },
            }
        )
    finally:
        await queue.put(None)  # unblocks the SSE generator if it's still listening
        saved_public_id = await _persist_report(
            transcript, keyword, signals, results, raw_score, gated_verdict,
            session_id, ip, filter_result,
            public_id=public_id,
            verifier=verifier_output, adjusted_score=adjusted_score,
            gating_score=gating_score, verdict_would_flip=verdict_would_flip,
        )
        if saved_public_id and not VERIFIER_PENALTY_ENABLED:
            # Shadow mode: Verifier hasn't run yet — kick it off now,
            # independent of this task's own completion, and patch the
            # doc when it lands. Never blocks the SSE stream.
            _spawn_verifier_shadow(saved_public_id, raw_score, results)


def spawn_pipeline(
    queue: "asyncio.Queue[dict | None]",
    transcript: str,
    keyword: str,
    signals: dict,
    session_id: str | None = None,
    ip: str | None = None,
    filter_result: dict | None = None,
) -> asyncio.Task:
    task = asyncio.create_task(
        _run_pipeline(queue, transcript, keyword, signals, session_id, ip, filter_result)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def stream_analysis(
    transcript: str,
    keyword: str,
    signals: dict,
    *,
    session_id: str | None = None,
    ip: str | None = None,
    filter_result: dict | None = None,
) -> AsyncGenerator[str, None]:
    """
    Yields SSE-formatted strings as each agent completes.
    The actual pipeline runs in an independent task (see spawn_pipeline) —
    this generator only relays it; disconnecting does not stop the save.
    """
    queue: "asyncio.Queue[dict | None]" = asyncio.Queue()
    spawn_pipeline(queue, transcript, keyword, signals, session_id, ip, filter_result)

    while True:
        item = await queue.get()
        if item is None:
            break
        yield f"data: {json.dumps(item)}\n\n"

    yield "data: [DONE]\n\n"
