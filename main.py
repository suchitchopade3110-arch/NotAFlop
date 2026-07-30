from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import phase1, phase2, phase3, phase4
from services import mongo


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo.connect()
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


@app.get("/health")
async def health():
    return {"status": "ok"}
