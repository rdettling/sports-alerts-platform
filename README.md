# Sports Alerts Platform

Sports Alerts is a production-style NBA alerts app with a separated web/API/worker architecture.

Production site: [https://livegamealerts.com](https://livegamealerts.com)

## What Works Today

- Email/password auth with JWT session.
- **Games** view with live/today/following filters.
- Moneyline odds display (book + no-vig win %) when odds are available.
- **Following** view for teams and games, including recently completed games.
- **Alerts** view for rule toggles, close-game threshold settings, and alert history filters.
- Background worker ingest, rule evaluation, and email/log delivery pipeline.
- Optional **Test** tab (when `DEV_MODE=true`) for manual dev email triggers.

## Stack

- `apps/web`: React + Vite
- `services/api`: FastAPI + SQLAlchemy + Alembic
- `services/worker`: polling, odds ingest, alert evaluation, delivery
- `infra/docker-compose.yml`: local orchestration

## Quick Start (Local)

1. `make setup`
2. Fill required values in `.env`
3. `make rebuild`
4. Open:
   - Web: `http://localhost:5173`
   - API docs: `http://localhost:8000/docs`
   - API health: `http://localhost:8000/healthz`

## Core Commands

- `make setup` — bootstrap `.env` + local deps
- `make up` — start existing images/containers
- `make rebuild` — rebuild images and start fresh app containers
- `make down` — stop stack, keep DB volume
- `make reset` — stop stack and remove DB volume
- `make logs` — tail all logs (`SERVICE=api|worker|web|db` optional)
- `make test` — run API + worker + web checks

## Docs

- App functionality: `docs/functionality.md`
- Architecture: `docs/architecture.md`
- Local development: `docs/local-development.md`
- Environment variables: `docs/environment-variables.md`
- Render deployment: `docs/deployment-render.md`
- Troubleshooting runbook: `docs/runbook.md`
- Product roadmap: `docs/roadmap.md`
