# Local Development

## Prerequisites

- Docker Desktop (running)
- `uv`
- Node.js 20+

## First-Time Setup

1. `make setup`
2. Edit `.env` (required variables documented in `docs/environment-variables.md`)
3. `make rebuild`

## Daily Workflow

- Start: `make up`
- Stop: `make down`
- Logs: `make logs` (or `make logs SERVICE=worker`)
- Tests: `make test`

Use `make rebuild` when Dockerfiles/dependencies change.
Use `make reset` only when you intentionally want to wipe local DB data.

## Local Verification Checklist

- API health responds: `GET http://localhost:8000/healthz`
- API docs open: `http://localhost:8000/docs`
- Frontend opens: `http://localhost:5173`
- Magic-link sign-in works
- Games/follows load
- Worker logs show ingest cycles

## Notes

- API root (`/`) returns `404` by design.
- If `ODDS_ENABLED=false`, games still load but odds columns show empty values.
- If `DEV_MODE=true`, frontend shows a `Test` tab and API exposes `/alerts/dev/test-email`.
