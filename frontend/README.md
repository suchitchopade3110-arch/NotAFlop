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

## Known backend gap (Phase 4 item)

`POST /api/phase2/validate` requires a `keyword` up front to gather live
market signals, but the only keyword extractor on the backend
(`services/keyword_extractor.py`) runs inside `POST /api/phase3/analyze`
itself as a fallback for an omitted `keyword` — there's no standalone,
callable extraction step between Phase 1 (filter) and Phase 2 (gather
signals). `lib/utils/keyword.ts` works around this with a client-side
heuristic used only to seed the signal-gathering call; the score-bearing
report still uses the backend's own LLM-extracted keyword (this app
omits `keyword` from the analyze request so the backend re-derives it).
The real fix is a callable extraction endpoint, or letting
`/api/phase2/validate` accept a transcript directly.
