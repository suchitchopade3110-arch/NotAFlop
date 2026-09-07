"""
Per-Groq-call token/cost tracking (Phase 1, C3). Groundwork for Phase 2,
where per-scheduled-job cost has to be instrumented from the first run
rather than discovered on the bill.

services.groq_client.chat() records one entry per call (agent, model,
prompt/completion tokens, computed cost) into a per-run ledger; the
orchestrator reads the total once a report's agents have all finished and
persists it as ReportDocument.report_cost_usd.

The ledger is a contextvar holding a plain list, seeded once per report
run (orchestrator.graph._run_pipeline calls start_cost_tracking() before
spawning any agent task). contextvars copy their *value* into each child
asyncio.Task at creation time — for a list, that copied value is a
reference to the SAME list object, so every agent task appending to "its"
ledger is actually appending to the one shared list the run started with.
A chat() call made with no ledger started for its context (e.g. Phase 1's
narrow_problem/pitch_clarity filters, which aren't part of a report run)
is a no-op here — cost is still computed and logged either way, just not
accumulated into a report total that doesn't exist for that call.

Purely observability, like signal_quality/conflicts (B3/B4) — never used
for gating or scoring.
"""
import contextvars

from core.config import (
    GROQ_DEFAULT_COMPLETION_PRICE_PER_M,
    GROQ_DEFAULT_PROMPT_PRICE_PER_M,
    GROQ_PRICE_PER_MILLION_TOKENS,
)

_ledger: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar("groq_cost_ledger", default=None)


def start_cost_tracking() -> None:
    """Call once per report-generation run, before spawning any agent
    tasks — see orchestrator.graph._run_pipeline."""
    _ledger.set([])


def compute_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = GROQ_PRICE_PER_MILLION_TOKENS.get(model, {})
    prompt_price = prices.get("prompt", GROQ_DEFAULT_PROMPT_PRICE_PER_M)
    completion_price = prices.get("completion", GROQ_DEFAULT_COMPLETION_PRICE_PER_M)
    cost = (prompt_tokens / 1_000_000) * prompt_price + (completion_tokens / 1_000_000) * completion_price
    return round(cost, 8)


def record_call(agent_name: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Appends one entry to the current run's ledger, if one was started
    for this context (see module docstring) — always returns the computed
    cost for this one call regardless, so callers can log it either way."""
    cost_usd = compute_cost_usd(model, prompt_tokens, completion_tokens)
    ledger = _ledger.get()
    if ledger is not None:
        ledger.append({
            "agent": agent_name,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost_usd,
        })
    return cost_usd


def get_ledger() -> list[dict]:
    return list(_ledger.get() or [])


def get_total_cost_usd() -> float:
    return round(sum(entry["cost_usd"] for entry in get_ledger()), 8)


def cost_since(marker_len: int) -> float:
    """Total cost of ledger entries added since an earlier get_ledger()
    call returned a list of that length — used to isolate the shadow
    Verifier's own incremental cost (it runs in a separate task, spawned
    after the wave-1 total was already read and persisted)."""
    ledger = get_ledger()
    return round(sum(entry["cost_usd"] for entry in ledger[marker_len:]), 8)
