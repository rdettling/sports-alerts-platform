# Local Development

## Prerequisites

- Docker Desktop
- `uv`
- Node.js 24

The standard local path is the Docker-based stack defined in `infra/docker-compose.yml`.

## First-Time Setup

1. Run `make setup`
2. Review and edit `.env`
3. Run `make rebuild`

The generated `.env` template and required config groups are documented in [configuration.md](configuration.md).

## Local URLs

- Web: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/healthz`

## Daily Workflow

- Start the stack: `make up`
- Rebuild and restart app containers: `make rebuild`
- Stop the stack: `make down`
- Tail all logs: `make logs`
- Tail one service: `make logs SERVICE=worker`
- Wipe local DB volumes: `make reset`

Use `make reset` only when you intentionally want to discard local database state.

## Testing

Primary repo check:

- `make test`

If you want narrower service checks:

- API: `cd services/backend && uv run pytest -q tests/api`
- Worker: `cd services/backend && uv run pytest -q tests/worker`
- Web build: `cd apps/web && npm run build`

The destructive reset path has an opt-in Postgres integration test. It only accepts a local Postgres URL whose database name contains `reset_test`:

```sh
cd services/backend
POSTGRES_RESET_TEST_DATABASE_URL=postgresql+psycopg://sports:sports@127.0.0.1:5432/sports_reset_test \
  uv run pytest -q tests/api/test_postgres_reset.py
```

## Local Verification Checklist

- `GET /healthz` returns `200`
- `/docs` loads for the API
- the web app loads at `:5173`
- magic-link and one-time-code sign-in work
- the public `Games` and `Teams` sections load
- authenticated follow controls and the `Alerts` section load
- worker logs show ingest activity
- admin tools appear only for an admin user

## Local Behavior Notes

- API root `/` returns `404` by design
- The API seeds teams and ensures the bootstrap admin user on startup
- If `ODDS_API_KEY` is blank, games still ingest and alerts still evaluate; only odds fetches are skipped
- Local development is safest with `DELIVERY_MODE=log` unless you explicitly want real email delivery
