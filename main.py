from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.cors import resolve_cors_origins
from core.logging import configure_logging
from core.middleware import RequestIDMiddleware
from repositories import (
    account_repository,
    criteria_repository,
    evidence_repository,
    idea_repository,
    report_repository,
    session_repository,
    snapshot_repository,
)
from routers import internal, phase1, phase2, phase3, phase4, phase5, reports, v1_auth, v1_ideas
from services import health, mongo

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo.connect()
    await report_repository.ensure_indexes()
    await session_repository.ensure_indexes()
    # Phase 2 (additive) — evidence-log collections.
    await account_repository.ensure_indexes()
    await idea_repository.ensure_indexes()
    await snapshot_repository.ensure_indexes()
    await criteria_repository.ensure_indexes()
    await evidence_repository.ensure_indexes()
    yield
    await mongo.disconnect()


app = FastAPI(title="NotAFlop API", version="0.1.0", lifespan=lifespan)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=resolve_cors_origins(),  # C6: env-driven, see core/cors.py
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(phase1.router, prefix="/api/phase1", tags=["Phase 1 - Filter"])
app.include_router(phase2.router, prefix="/api/phase2", tags=["Phase 2 - Validate"])
app.include_router(phase3.router, prefix="/api/phase3", tags=["Phase 3 - Analyze"])
app.include_router(phase4.router, prefix="/api/phase4", tags=["Phase 4 - Gate"])
app.include_router(phase5.router, prefix="/api/phase5", tags=["Phase 5 - Plan & Build"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])
app.include_router(internal.router, prefix="/internal", tags=["Internal"])

# Phase 2 — everything new is namespaced under /v1, existing routes above
# are untouched (constraint #2).
app.include_router(v1_auth.router, prefix="/v1", tags=["Phase 2 - Identity"])
app.include_router(v1_ideas.router, prefix="/v1", tags=["Phase 2 - Ideas"])


@app.get("/health")
async def health_check():
    """Deep health check (Phase 1, C4) — see services/health.py. Fast
    (short per-dependency timeouts, cached briefly), never blocking, and
    one dependency's failure never cascades into another's check."""
    return await health.get_health()
