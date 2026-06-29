<div align="center">
<img src="https://raw.githubusercontent.com/suchitchopade3110-arch/NotAFlop/main/notaflop-logo.png" />
<br/>
<!-- Animated tagline banner -->
<img src="https://readme-typing-svg.demolab.com?font=Sora&weight=700&size=28&duration=3000&pause=1000&color=C9A84C&center=true&vCenter=true&width=600&lines=Validate+before+you+build.;11+AI+agents.+30+seconds.+Free.;Know+the+truth+about+your+idea." alt="Typing SVG" />
<br/><br/>
 
[![Status](https://img.shields.io/badge/status-building-C9A84C?style=for-the-badge&labelColor=0D0D0D)](https://github.com/suchitchopade3110-arch/NotAFlop)
[![License](https://img.shields.io/badge/license-MIT-C9A84C?style=for-the-badge&labelColor=0D0D0D)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0D0D0D?style=for-the-badge&logo=fastapi&logoColor=C9A84C)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python_3.14-0D0D0D?style=for-the-badge&logo=python&logoColor=C9A84C)](https://python.org)
[![GROQ](https://img.shields.io/badge/GROQ_Inference-0D0D0D?style=for-the-badge&logoColor=C9A84C)](https://groq.com)
 
</div>
---
 
<div align="center">
```
35–42% of startups fail because they build products nobody wants.
NotAFlop exists to stop that.
```
 
</div>
---
 
## What is NotAFlop?
 
NotAFlop is a **free, evidentiary, multi-agent startup validator**. You pitch your idea. 11 specialist AI agents tear it apart across every dimension a VC would care about — backed by live market data, not hallucinated encouragement. You get a scored verdict in under 30 seconds.
 
**Not a business plan generator. Not a cheerleader. A stress-tester.**
 
---
 
## How it works
 
```
Your Pitch
    │
    ▼
┌─────────────────────────────────────────────┐
│  PHASE 1 — FILTER                           │
│  Narrow Problem Filter + Pitch Clarity      │
│  Fails fast. Saves compute.                 │
└──────────────────┬──────────────────────────┘
                   │ pass
                   ▼
┌─────────────────────────────────────────────┐
│  PHASE 2 — SMART DATA LAYER                 │
│  Google Trends · Reddit · Hacker News       │
│  Product Hunt · Wellfound                   │
│  Redis-cached · 24hr TTL                    │
└──────────────────┬──────────────────────────┘
                   │ signals
                   ▼
┌─────────────────────────────────────────────┐
│  PHASE 3 — 11 AGENTS IN PARALLEL            │
│                                             │
│  Problem ──── Solution ──── TAM             │
│  Team ──────── Moat ──── Unit Econ          │
│  GTM ───────── Risk ──── Timing             │
│  Ask ───────── YC Signal                   │
│                                             │
│  LLaMA 3.3-70B · DeepSeek-R1-70B via GROQ  │
│  Streamed via SSE as each agent completes   │
└──────────────────┬──────────────────────────┘
                   │ scores
                   ▼
┌─────────────────────────────────────────────┐
│  PHASE 4 — GATE                             │
│  VC-weighted aggregation                    │
│  Problem ×1.2 · Solution ×1.1 · Ask ×0.8   │
│                                             │
│  ≥70 → GO    50–69 → PIVOT    <50 → NO-GO  │
└──────────────────┬──────────────────────────┘
                   │ go / pivot
                   ▼
┌─────────────────────────────────────────────┐
│  PHASE 5 — PLAN & BUILD                     │
│  90-day MVP roadmap                         │
│  Team role recommendations                  │
│  GTM + distribution strategy               │
│  Full PDF report                            │
└─────────────────────────────────────────────┘
```
 
---
 
## The 11 Agents
 
| Agent | Model | Evaluates |
|---|---|---|
| 🔴 Problem | DeepSeek-R1-70B | Is the pain real, specific, frequent? |
| 🟡 Solution | DeepSeek-R1-70B | Does it map directly to the pain? |
| 📊 TAM | LLaMA 3.3-70B | Is the market large and reachable? |
| 👤 Team | LLaMA 3.3-70B | Founder-market fit + execution edge |
| 🏰 Moat | LLaMA 3.3-70B | Defensible advantage that compounds |
| 💰 Unit Economics | LLaMA 3.3-70B | Pricing, margins, retention |
| 📣 GTM | LLaMA 3.3-70B | Specific first customer + credible channels |
| ⚠️ Risk | DeepSeek-R1-70B | Technical, regulatory, competitive threats |
| ⏱️ Timing | LLaMA 3.3-70B | Is the market ready right now? |
| 🎯 Ask | DeepSeek-R1-70B | Is the funding need realistic? |
| ✨ YC Signal | DeepSeek-R1-70B | YC-style traits: acute pain, fast iteration |
 
**Scoring weights:** Problem `×1.2` · Solution `×1.1` · Risk/Timing `×0.95` · Team/Moat `×0.90` · Ask `×0.80`
 
---
 
## Tier Breakdown
 
### Tier 1 — 60-Second Viability Check
> Free. Always. 3 reports/day per user.
 
Viability score `/100` · Go/Pivot/No-Go verdict · Pitch clarity `/10` · YC benchmark · Top 3 risks
 
### Tier 2 — Deep Dive *(unlocked on score ≥ 50)*
> Free. Unlocked by passing Tier 1.
 
90-day MVP roadmap · Launch checklist · 12-month growth milestones · Revenue model options
 
### Tier 3 — Execution Layer
> Free. PDF export is the premium upsell trigger.
 
Team role recommendations · Top 3 marketing channels · Virality loop design · Downloadable full PDF report
 
---
 
## Tech Stack
 
```
Frontend          Backend           Inference         Data
─────────         ──────────        ─────────         ──────────────
Next.js 15        FastAPI           GROQ LPU          Google Trends
Tailwind CSS      LangGraph         LLaMA 3.3-70B     Reddit (PRAW)
Zustand           Celery + Redis    DeepSeek-R1-70B   Hacker News
Recharts          MongoDB Atlas     Qwen-32B          Product Hunt
SSE streaming     Pinecone                            Wellfound
```
 
---
 
## Running Locally
 
**Prerequisites:** Python 3.12+, GROQ API key
 
```bash
# Clone
git clone https://github.com/suchitchopade3110-arch/NotAFlop.git
cd NotAFlop/notaflop-backend
 
# Setup venv
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux
 
# Install
pip install -r requirements.txt
 
# Configure
cp .env.example .env
# Add your GROQ_API_KEY to .env
 
# Run
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
 
API docs: `http://127.0.0.1:8000/docs`
 
> **Note:** Redis is optional. The app falls back to in-memory cache automatically if Docker is not running.
 
---
 
## Environment Variables
 
```env
GROQ_API_KEY=your_key_here
 
# Optional — data sources (stubs work without these)
APIFY_TOKEN=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
PRODUCT_HUNT_TOKEN=
 
# Optional — Redis (falls back to in-memory)
REDIS_URL=redis://localhost:6379
```
 
---
 
## Project Structure
 
```
notaflop-backend/
├── main.py                        # FastAPI app + router registration
├── core/
│   └── config.py                  # Centralized model + env config
├── agents/
│   ├── base_agent.py              # BaseAgent ABC + GROQ chat loop
│   ├── specialist_agents.py       # 11-agent registry
│   ├── narrow_problem.py          # Phase 1 filter
│   ├── pitch_clarity.py           # Phase 1 filter
│   └── [problem|solution|tam...].py
├── orchestrator/
│   ├── graph.py                   # LangGraph fan-out + SSE streaming
│   └── state.py                   # GraphState + AgentOutput TypedDicts
├── routers/
│   ├── phase1.py                  # /api/phase1 — filter
│   ├── phase2.py                  # /api/phase2 — smart data
│   └── phase3.py                  # /api/phase3 — analyze + stream
├── services/
│   ├── groq_client.py             # GROQ async chat wrapper
│   ├── cache.py                   # Redis + in-memory fallback
│   ├── smart_data_layer.py        # asyncio.gather across 5 sources
│   └── data_sources/
│       ├── google_trends.py
│       ├── reddit.py
│       ├── hacker_news.py
│       ├── product_hunt.py
│       └── wellfound.py
└── models/
    └── schemas.py                 # Pydantic request/response models
```
 
---
 
## Roadmap
 
- [x] Phase 1 — Filter agents (Narrow Problem + Pitch Clarity)
- [x] Phase 2 — Smart Data Layer (5 sources, Redis + in-memory cache)
- [x] Phase 3 — 11-agent LangGraph orchestrator + SSE streaming
- [ ] Phase 4 — Gate (clean verdict layer + score breakdown API)
- [ ] Phase 5 — Plan & Build (90-day roadmap + team + distribution)
- [ ] Real API keys (Apify, Reddit, Product Hunt, Wellfound)
- [ ] Frontend (Next.js 15 + Obsidian Gold design system)
- [ ] Product Hunt launch
---
 
## Why Free Forever?
 
Because the founders who need this most can't afford $29/report. Preuve AI charges per validation. Validator AI hallucinates. IdeaBuddy has no live data. NotAFlop has all three — live evidence, rigorous agents, structured roadmap — and it's free.
 
The only metric that matters: **founders who validated with NotAFlop and successfully launched within 12 months.**
 
---
 
<div align="center">
**Built for founders who'd rather know the truth than waste a year.**
 
<br/>
[![Star this repo](https://img.shields.io/github/stars/suchitchopade3110-arch/NotAFlop?style=for-the-badge&color=C9A84C&labelColor=0D0D0D&label=⭐%20Star%20this%20repo)](https://github.com/suchitchopade3110-arch/NotAFlop)
 
<sub>NotAFlop · Validate before you build · 2026</sub>
 
</div>
 
