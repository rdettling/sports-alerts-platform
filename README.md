# Sports Alerts Platform

Sports Alerts is an NBA alerting app with:

- `apps/web`: React + Vite frontend
- `services/api`: FastAPI backend
- `services/worker`: background ingest + alert worker
- `infra/docker-compose.yml`: local runtime stack

## Quick Start

Prerequisites:

- Docker Desktop
- `uv`
- Node.js 20+

1. Initialize local deps and `.env`:
   - `make setup`
2. Start services:
   - `make rebuild`
3. Open apps:
   - Web: `http://localhost:5173`
   - API docs: `http://localhost:8000/docs`
   - API health: `http://localhost:8000/healthz`

## Daily Commands

- `make up` — start stack from existing images
- `make down` — stop stack (keeps DB data)
- `make logs` — tail logs for all services
- `make logs SERVICE=api` — tail one service
- `make ps` — show service status
- `make restart SERVICE=worker` — restart one service
- `make test` — run API, worker, and web checks

## Local Secrets

- Keep real secrets in local `.env` only (gitignored).
- Minimum local `.env`:

```env
JWT_SECRET_KEY=replace-with-long-random-string
```

- Optional for game odds in the dashboard (used by worker ingest):

```env
ODDS_API_KEY=your_the_odds_api_key
```

- Optional for local email testing via the `Test` tab:

```env
DEV_MODE=true
DELIVERY_MODE=email
FROM_EMAIL=alerts@your-domain.com
RESEND_API_KEY=your_resend_api_key
```

## Deploy URLs

- API root (`/`) returns `404` by design.
- Use `.../healthz` and `.../docs` for API checks.

## Further Docs

- Architecture: `docs/architecture.md`
- Local/dev operations: `docs/local-development.md`
- Deployment (Render + Neon): `docs/deployment-render.md`
- Environment variables: `docs/environment-variables.md`
- Archived plan: `docs/archive/sports_alerts_v1_plan.md`
