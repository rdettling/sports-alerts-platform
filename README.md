# Sports Alerts Platform

Milestone 1 baseline for an NBA alerts platform with:

- `apps/web`: React + Vite frontend
- `services/api`: FastAPI API + Postgres migrations
- `services/worker`: background poller skeleton
- `infra/docker-compose.yml`: local stack

## Quick start

Prerequisite: Docker Desktop installed and running.

1. Install dependencies and create `.env`:
   - `make setup`
2. Start the stack:
   - `make up`
3. Services:
   - Web: `http://localhost:5173`
   - API: `http://localhost:8000`
   - API docs: `http://localhost:8000/docs`

## API endpoints (Milestone 1)

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `GET /teams`
- `GET /games`
- `GET /healthz`

## Testing

Python tests live in `services/api/tests` and `services/worker/tests`.

Run all checks:

- `make test`

Run a specific area:

- `make test-api`
- `make test-worker`
- `make test-web`

See all commands:

- `make help`

## Dependency management

Python dependencies are managed with `uv` via `pyproject.toml` + `uv.lock` in each service:

- `services/api/pyproject.toml`
- `services/worker/pyproject.toml`

Common commands:

- `uv lock` (update lockfile after dependency changes)
- `uv sync` (install runtime deps)
- `uv sync --group dev` (install test/dev deps)

## Notes

- The worker includes a provider abstraction (`fetch_schedule`, `fetch_game_updates`) and a placeholder adapter.
- Alert rule evaluation and email delivery are intentionally deferred to later milestones.
