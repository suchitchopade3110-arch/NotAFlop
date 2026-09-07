# NotAFlop — Frontend

Next.js 15 (App Router) + TypeScript + Tailwind v4 + Zustand. Consumes the
existing FastAPI backend in the repo root — no backend routes were added
or changed for this phase.

## Setup

```
cd frontend
cp .env.example .env.local   # point NEXT_PUBLIC_API_BASE_URL at the backend
npm install
npm run dev
```

## Design system

`app/globals.css` documents the full Obsidian Gold token plan (palette,
type scale, spacing, layout concepts) at the top of the file.

## Known backend gaps (Phase 4 items)

1. **No standalone keyword extraction.** `POST /api/phase2/validate`
   requires a `keyword` up front to gather live market signals, but the
   only keyword extractor on the backend (`services/keyword_extractor.py`)
   runs inside `POST /api/phase3/analyze` itself as a fallback for an
   omitted `keyword` — there's no standalone, callable extraction step
   between Phase 1 (filter) and Phase 2 (gather signals).
   `lib/utils/keyword.ts` works around this with a client-side heuristic
   used only to seed the signal-gathering call; the score-bearing report
   still uses the backend's own LLM-extracted keyword (this app omits
   `keyword` from the analyze request so the backend re-derives it). The
   real fix is a callable extraction endpoint, or letting
   `/api/phase2/validate` accept a transcript directly.

2. **No durable waitlist/signup capture.** The coming-soon page (D6) and
   the claim prompt (B5) are the only two places this app collects an
   email address pre-verdict-claim, and the only backend route that
   accepts one is `POST /v1/auth/claim` — it issues a 15-minute magic
   link rather than durably storing the address; nothing lands in the
   `accounts` collection until that link is clicked. For the claim
   prompt (after a real verdict) that's the intended design. For the
   coming-soon page it's a mismatch: most pre-launch signups won't click
   a "your idea log" link before launch, so most of them are lost. The
   real fix is a dedicated, durable signup-capture endpoint.

3. **Streaming reconnect has no resume point.** `POST /api/phase3/analyze`
   returns SSE over a plain POST with no job id and no way to resume an
   in-progress stream — the pipeline keeps running server-side after a
   client disconnect (by design, see `orchestrator/graph.py`), but the
   frontend has no way to reattach to it. `lib/hooks/use-validation-flow.ts`
   works around this by polling `GET /api/sessions/{sid}/reports` for a
   newly-completed report after a drop, which works but is a poll, not a
   resume. The real fix is a job id the client could reconnect a stream
   to, or a lightweight "is report X done yet" endpoint.
