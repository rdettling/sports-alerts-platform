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

- `cd services/api && pytest`
- `cd services/worker && pytest`

## Notes

- The worker includes a provider abstraction (`fetch_schedule`, `fetch_game_updates`) and a placeholder adapter.
- Alert rule evaluation and email delivery are intentionally deferred to later milestones.
