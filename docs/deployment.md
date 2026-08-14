# Deployment

This repo deploys cleanly as four parts:

- a web frontend
- an API service
- a background worker
- a Postgres database

The current reference deployment style is static frontend hosting plus two containerized Python services backed by managed Postgres. Render + Neon is a reasonable fit, but the repo is not coupled to those providers.

## Reference Topology

- Frontend: static hosting for `apps/web`
- API: containerized FastAPI service
- Worker: containerized long-running background process
- Database: Postgres

The worker and API should point at the same database and the same logical environment.

## API Service

Deploy the API from `services/api/Dockerfile`.

Requirements:

- Run `alembic upgrade head` before serving traffic
- Expose the app on the configured host/port
- Provide all required API env vars from [configuration.md](configuration.md)

Health checks:

- `GET /healthz` should return `200`
- `GET /docs` should load the OpenAPI docs

## Worker Service

Deploy the worker from `services/worker/Dockerfile`.

Run:

```sh
uv run python -m worker.main
```

Requirements:

- Point at the same database as the API
- Provide worker env vars from [configuration.md](configuration.md)
- Keep it running continuously; this is not a scheduled job container

Behavior notes:

- If `ODDS_ENABLED=false`, the worker still ingests games and evaluates alerts
- League enable/disable state is read from the database, so runtime scope can change without redeploying

## Frontend Service

Build and publish `apps/web`.

Reference build:

```sh
npm ci --include=optional
npm run build
```

Required env:

- `VITE_API_BASE_URL=https://<api-origin>`

If you host the frontend as a single-page app, configure route fallback so browser refreshes on nested routes keep working.

## Database

Use Postgres 16 or a compatible managed Postgres offering.

Requirements:

- A persistent database shared by API and worker
- Network access from both services
- A connection string compatible with SQLAlchemy / psycopg

The repo stores both user data and disposable sports-domain state in Postgres. User identity matters more than sports data, so operationally it is acceptable to reset sports-domain data if needed, but do not treat user/auth data casually.

The current baseline is intentionally self-contained. Replacing it requires an explicit full schema reset during a maintenance window; do not point a rewritten baseline at an existing schema.

## Post-Deploy Checks

After a deploy:

1. Open the frontend
2. Confirm `GET /healthz` is healthy
3. Confirm magic-link and one-time-code sign-in work
4. Confirm public games and teams load, then verify authenticated follow controls
5. Confirm worker logs show sync activity
6. Verify controlled Email, Push, and Both test alerts for the admin account
7. Confirm a push notification opens the Games page and history shows channel-specific delivery chips
8. If Neon integration is configured, confirm the admin DB stats view can load usage data
