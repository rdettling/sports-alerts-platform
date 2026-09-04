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

## Service Release Order

Configure the worker API URL and matching shared secret before starting worker publication. Release changes to worker/API/frontend contracts in this order:

1. API, so worker update endpoints and frontend response fields are available
2. Worker, so it publishes the expected game notifications and schedule reports
3. Frontend, so it can consume the updated API

Keep one worker and one Uvicorn process on one API instance. SSE, the game cache, and schedule reports are process-local; see [architecture](architecture.md#design-constraints). API restarts disconnect streams and discard schedule reports. Browsers must reconnect and fetch current games; Admin may show Schedule unavailable until the worker next reports, potentially 12 hours later. Worker restarts clear remembered success times, run an immediate catalog cycle, and reset the 12-hour catalog anchor.

### Shared Catalog Schedule Cutover

When releasing the shared catalog schedule, follow API → worker → frontend. Reports require `next_catalog_at` and accept the `queued` job state. Old worker reports may be rejected during the API/worker cutover; temporary Schedule unavailable is expected. This cutover needs no new configuration, dependency, or database migration.

Remove any obsolete `SCHEDULER_IDLE_MAX_SLEEP_SECONDS` override from the worker environment; the maximum wait uses `CATALOG_SYNC_INTERVAL_SECONDS` instead.

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

Capture a fresh Neon usage baseline using the [database usage runbook](runbook.md#reviewing-database-awake-time-and-waste). Confirm API and worker log `Database usage logging started`, then check for nonempty summaries after five minutes of activity. Compare at least a day of logs from the same deployed revision before judging database savings.

After a deploy:

1. Open the frontend
2. Confirm `GET /healthz` is healthy
3. Confirm magic-link and one-time-code sign-in work
4. Confirm public games and teams load, then verify authenticated follow controls
5. Confirm worker logs show sync activity
6. Verify email-only, push-only, combined, and no-delivery test states for the admin account
7. Confirm a push notification opens the Games page and history shows channel-specific delivery chips
8. If Neon integration is configured, confirm the admin DB stats view can load usage data
9. Observe a natural worker change and confirm `/updates/games` delivers it and the visible Games screen updates within five seconds under healthy networking
10. On an actual iPhone Home Screen installation, check lock/unlock, app switching, and offline/online recovery. The stream should close while hidden/offline and reopen with a catch-up read on return
11. Confirm a desktop client reconnects and refreshes after a normal API deployment; opening the stream must also fetch state to cover updates missed during connection establishment
12. In local testing, suppress a notification on a feed already showing a live game and confirm the visible fallback recovers within two minutes; confirm concurrent dashboard readers share one cache fill. Also verify a quiet screen does not read games every minute and checks at an upcoming scheduled start. Quiet-period missed events can take up to 30 minutes to recover. Do not change production scores or disable production publishing for this check
13. Compare Admin's single Next catalog refresh deadline and per-league outcomes with `Catalog cycle queued` and `Job completed` logs; use the [schedule troubleshooting procedure](runbook.md#admin-league-sync-times) for missing or stale reports
14. Verify Admin makes no automatic requests while idle, across tab changes, or on foreground/reconnect events, using the [Admin refresh checks](runbook.md#admin-data-is-stale-or-refreshing-unexpectedly)
15. Review an overnight quiet period for worker scans between scheduled jobs and correlate activity with Neon wake/sleep history using the database usage runbook
