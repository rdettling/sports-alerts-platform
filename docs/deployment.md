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

Deploy the API from `services/backend/Dockerfile` using its default command.

Requirements:

- Run `alembic upgrade head` before serving traffic
- Expose the app on the configured host/port
- Provide all required API env vars from [configuration.md](configuration.md)
- Set `LIVE_UPDATE_SECRET` to the same generated secret used by the worker

Health checks:

- `GET /healthz` should return `200`
- `GET /docs` should load the OpenAPI docs

## Worker Service

Deploy the worker from `services/backend/Dockerfile`.

Run:

```sh
/opt/venv/bin/python -m app.worker.main
```

Requirements:

- Point at the same database as the API
- Provide worker env vars from [configuration.md](configuration.md)
- Keep it running continuously; this is not a scheduled job container
- Set `LIVE_UPDATE_API_URL` to the API origin and `LIVE_UPDATE_SECRET` to the API's value

Behavior notes:

- If `ODDS_API_KEY` is blank, the worker still ingests games and evaluates alerts
- Competition enable/disable state is read from the database, so runtime scope can change without redeploying

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

## Live Update Rollout

Live updates require no database migration or additional service. Configure the shared secret before deploying the feature, then deploy in this order:

1. API, so both live update endpoints exist
2. Worker, so changed commits begin publishing
3. Frontend, so browsers begin opening SSE connections

Notification failure never fails or retries a completed sync. The frontend keeps a ten-minute live fallback and a hard two-minute minimum between `/games` reads.

## Database

Use Postgres 16 or a compatible managed Postgres offering.

Requirements:

- A persistent database shared by API and worker
- Network access from both services
- A connection string compatible with SQLAlchemy / psycopg

The repo stores both user data and disposable sports-domain state in Postgres. The current migration chain starts from the self-contained `0001_baseline`; databases already on that baseline upgrade normally through later revisions. Databases created from an older copy of `0001_baseline` still have no compatibility path and require the reset procedure below.

Runtime code supports only the latest Alembic revision. Apply `alembic upgrade head` before serving the new release rather than adding application code that handles both old and new schema shapes.

### Clean-Baseline Cutover

Use this procedure only when replacing an incompatible pre-baseline or older-baseline database. Normal upgrades from the current `0001_baseline` must use `alembic upgrade head` and preserve existing data.

1. Put the application into a maintenance window and pause the worker.
2. Build the new release or check out the new commit without starting its API or worker.
3. Verify that `DATABASE_URL` points to the intended production database.
4. From `services/backend` in the new release, run:

   ```sh
   uv run python scripts/reset_database.py --yes
   ```

5. Start the new API. Its automatic Alembic command upgrades the reset database to the latest revision.
6. Deploy the worker and frontend. Deploy the frontend with the API because the old `/leagues` contract no longer exists.
7. Sign in with the bootstrap admin email, resubscribe notification devices, and complete the checks below.

Do not deploy the new API first and plan to reset afterward: its startup migration will fail before the service can become healthy.

## Post-Deploy Checks

After a deploy:

1. Open the frontend
2. Confirm `GET /healthz` is healthy
3. Confirm magic-link and one-time-code sign-in work
4. Confirm public games and teams load, then verify authenticated follow controls
5. Confirm worker logs show sync activity
6. Verify email-only, push-only, combined, and no-delivery test states for the admin account
7. Confirm a push notification opens the Games page and history shows channel-specific delivery chips
8. If Neon integration is configured, confirm the admin DB stats view can load usage data
9. Confirm `/updates/games` remains connected and changed worker jobs prompt no more than one `/games` read every two minutes per visible client
