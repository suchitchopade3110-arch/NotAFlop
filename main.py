from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from repositories import report_repository, session_repository
from routers import phase1, phase2, phase3, phase4, phase5, reports
from services import mongo


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo.connect()
    await report_repository.ensure_indexes()
    await session_repository.ensure_indexes()
    yield
    await mongo.disconnect()


app = FastAPI(title="NotAFlop API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # update for prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(phase1.router, prefix="/api/phase1", tags=["Phase 1 - Filter"])
app.include_router(phase2.router, prefix="/api/phase2", tags=["Phase 2 - Validate"])
app.include_router(phase3.router, prefix="/api/phase3", tags=["Phase 3 - Analyze"])
app.include_router(phase4.router, prefix="/api/phase4", tags=["Phase 4 - Gate"])
app.include_router(phase5.router, prefix="/api/phase5", tags=["Phase 5 - Plan"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])


@app.get("/health")
async def health():
    return {"status": "ok"}
