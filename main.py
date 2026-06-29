from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import phase1, phase2, phase3

app = FastAPI(title="NotAFlop API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # update for prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(phase1.router, prefix="/api/phase1", tags=["Phase 1 - Filter"])
app.include_router(phase2.router, prefix="/api/phase2", tags=["Phase 2 - Validate"])
app.include_router(phase3.router, prefix="/api/phase3", tags=["Phase 3 - Analyze"])


@app.get("/health")
async def health():
    return {"status": "ok"}
