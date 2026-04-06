# Sports Alerts Platform

Milestone 1 baseline for an NBA alerts platform with:

- `apps/web`: React + Vite frontend
- `services/api`: FastAPI API + Postgres migrations
- `services/worker`: background poller skeleton
- `infra/docker-compose.yml`: local stack

## Quick start

1. Copy env vars:
   - `cp .env.example .env`
2. Start the stack:
   - `docker compose -f infra/docker-compose.yml up --build`
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

Example:

- `cd services/api && uv sync --group dev && uv run pytest`
- `cd services/worker && uv sync --group dev && uv run pytest`

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
