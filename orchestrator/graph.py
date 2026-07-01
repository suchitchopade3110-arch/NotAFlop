"""
LangGraph orchestrator for Phase 3 - Analyze.
Spawns all 11 agents in parallel via a single fan-out node.
Results stream back via an async generator consumed by the SSE endpoint.
"""
import asyncio
import json
from typing import AsyncGenerator

try:
    from langgraph.graph import END, StateGraph
except ModuleNotFoundError:
    END = None
    StateGraph = None

from agents.specialist_agents import ALL_AGENTS
from orchestrator.state import AgentOutput, GraphState
from services.gate import aggregate_results


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


async def stream_analysis(transcript: str, keyword: str, signals: dict) -> AsyncGenerator[str, None]:
    """
    Yields SSE-formatted strings as each agent completes.
    Runs agents in parallel and streams partial results as tasks finish.
    """
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
    results = {}
    errors = []
    pending = dict(tasks)

    while pending:
        done, _ = await asyncio.wait(list(pending.values()), return_when=asyncio.FIRST_COMPLETED)
        for fut in done:
            for name, task in list(pending.items()):
                if task is fut:
                    try:
                        result: AgentOutput = await task
                        results[name] = result
                        yield f"data: {json.dumps({'type': 'agent', 'payload': result})}\n\n"
                    except Exception as exc:
                        errors.append(f"{name}: {str(exc)}")
                        yield f"data: {json.dumps({'type': 'agent_error', 'payload': {'agent': name, 'error': str(exc)}})}\n\n"
                    del pending[name]
                    break

    final_score, verdict = aggregate_results(results)
    yield f"data: {json.dumps({'type': 'final', 'payload': {'score': final_score, 'verdict': verdict, 'errors': errors}})}\n\n"
    yield "data: [DONE]\n\n"
