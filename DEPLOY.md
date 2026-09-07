# Deploying NotAFlop (D5)

One deploy configuration that actually works: `docker-compose.prod.yml`
at the repo root runs the full stack — backend, frontend, Mongo, Redis —
from the `Dockerfile`s in the repo root (backend) and `frontend/`
(frontend). This is the one path documented and tested here; any managed
platform (Render, Fly.io, Railway, a VM) can run the same two images.

## Quick start (single host)

```bash
cp .env.prod.example .env   # fill in GROQ_API_KEY, CORS_ALLOWED_ORIGINS, etc.
docker compose -f docker-compose.prod.yml up -d --build
```

- Backend: `http://<host>:8000` (health check at `/health`)
- Frontend: `http://<host>:3000`

Put a reverse proxy (nginx, Caddy, your platform's load balancer) in
front of both for TLS and to route `notaflop.com` -> frontend:3000 and
`api.notaflop.com` -> backend:8000. `core/session.py`'s IP extraction
assumes exactly one trusted proxy in front of the app — see its module
docstring if you chain more than one.

## Environment variables

| Variable | Where | Required | Notes |
|---|---|---|---|
| `GROQ_API_KEY` | backend | yes | Powers every specialist agent call. |
| `MONGODB_URI` / `MONGODB_DB` | backend | yes | Set to `mongo:27017` automatically by the compose file; override for a managed Atlas cluster. |
| `REDIS_URL` | backend | yes | Set to `redis:6379` automatically by the compose file. |
| `ENVIRONMENT` | backend | yes | `production` outside local dev — this makes `CORS_ALLOWED_ORIGINS` mandatory (see `core/cors.py`). |
| `CORS_ALLOWED_ORIGINS` | backend | yes in prod | Comma-separated browser origins allowed to call the API — must include the frontend's public origin. |
| `FRONTEND_BASE_URL` | backend | yes | Where magic-link emails point (`/claim?token=...`) — must match `NEXT_PUBLIC_SITE_URL` below. |
| `ADMIN_API_KEY` | backend | recommended | Gates `/internal/*`. Unset = those routes 503 (fails closed). |
| `SNAPSHOT_SCHEDULER_ENABLED` | backend | recommended | `true` in production so scheduled re-scores and kill-criteria sweeps actually run. |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | yes | The backend's public origin. Baked in at build time — changing it means rebuilding the frontend image. |
| `NEXT_PUBLIC_SITE_URL` | frontend | yes | The frontend's own public origin — used for share links and OG metadata. |
| `NEXT_PUBLIC_POSTHOG_KEY` / `_HOST` | frontend | optional | Unset = analytics calls no-op (D1). |
| `NEXT_PUBLIC_COMING_SOON` | frontend | optional | `true` flips the root route to `/coming-soon` (D6) ahead of launch. |

See `.env.example` (backend) and `frontend/.env.example` for the full,
per-service list with defaults.

## Health checks

- Backend: `GET /health` — deep check (Mongo, Redis, Groq reachability),
  short per-dependency timeouts, never blocks (`services/health.py`).
  Both the backend `Dockerfile`'s `HEALTHCHECK` and the compose file
  poll this.
- Frontend: `GET /` — the `Dockerfile`'s `HEALTHCHECK` confirms the
  Next.js server itself responds; wire your platform's health check to
  the same path.

Point your platform's load balancer / uptime check at both.

## CI

`.github/workflows/ci.yml` runs on every push and PR: backend lint
(`ruff`, scoped to real errors) + `pytest`, and frontend lint (`eslint`)
+ typecheck (`tsc --noEmit`) + `next build`, as two independent jobs.
