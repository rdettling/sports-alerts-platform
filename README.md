# Sports Alerts Platform

Milestone 1 baseline for an NBA alerts platform with:

- `apps/web`: React + Vite frontend
- `services/api`: FastAPI API + Postgres migrations
- `services/worker`: background poller skeleton
- `infra/docker-compose.yml`: local stack

## Quick start

Prerequisite: Docker Desktop installed and running.

1. `make setup` (first time only: creates `.env` and installs local test deps)
2. `make rebuild` (build images and start services)
3. Open:
   - Web: `http://localhost:5173`
   - API: `http://localhost:8000`
   - API docs: `http://localhost:8000/docs`

## Which command should I use?

### Most common flows

- Resume project after reboot: `make up`
- Check if everything is running: `make ps`
- View logs while debugging: `make logs` or `make logs SERVICE=api`
- Stop services (keep DB/data): `make down`
- Rebuild after dependency/Dockerfile changes: `make rebuild`

### Destructive command (use carefully)

- `make reset` deletes Docker volumes, including Postgres data.
- After `make reset`, accounts/follows/history are gone and you must re-register users.

## Make command reference

- `make setup` — first-time machine setup for local testing.
- `make up` — start existing containers/images quickly.
- `make rebuild` — rebuild images, then start stack.
- `make down` — stop stack without deleting data.
- `make reset` — stop stack and delete volumes/data.
- `make logs` — stream all service logs.
- `make logs SERVICE=api` — stream one service logs (`api|worker|web|db`).
- `make ps` — show container status.
- `make restart SERVICE=worker` — restart one service.
- `make test` — run all tests/build checks.
- `make test-api` — run API tests.
- `make test-worker` — run worker tests.
- `make test-web` — run frontend build check.

## API endpoints (Milestone 1)

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `GET /teams`
- `GET /games`
- `GET /healthz`

## Testing

Python tests live in `services/api/tests` and `services/worker/tests`.

Install local dev dependencies before running host-side tests:

- `make setup`

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

Container runtime model:

- Dependencies are built into Docker images (not installed on every container start).
- API and worker run from a dedicated virtualenv at `/opt/venv` inside containers.
- Source code is bind-mounted for live editing, but dependency environments are not bind-mounted.

## Notes

- The worker includes a provider abstraction (`fetch_schedule`, `fetch_game_updates`) backed by ESPN NBA scoreboard ingestion for Milestone 3.
- Alert rule evaluation and email delivery are intentionally deferred to later milestones.

## Architecture notes

- `web` calls `api` for auth, follows, preferences, games, and alert history.
- `worker` polls NBA data, upserts game state, evaluates alert rules, and sends queued alerts.
- Deduplication is enforced in `sent_alerts` via unique `dedupe_key` (`user_id:game_id:alert_type`).
- API and worker are separate runtime services with shared Postgres state.

## Deployment prep checklist

- Set secure values in `.env` for `JWT_SECRET_KEY` and email provider credentials.
- Set `CORS_ALLOW_ORIGINS` to your deployed frontend domain.
- Build and run API/worker images from CI with pinned lockfiles.
- Run migrations before serving API traffic.
- Set `DELIVERY_MODE=email` only when provider credentials are configured.
