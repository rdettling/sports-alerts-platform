# Deployment

Deploy a static frontend and one always-on backend. The backend runs one Uvicorn process plus the scheduler and alert-delivery threads, sharing a local SQLite database.

## Backend on Render

- Build `services/backend/Dockerfile` from the repository root.
- Attach a persistent disk at `/var/data` to the paid web service.
- Set `DATABASE_URL=sqlite:////var/data/sports-alerts.db` and the secrets listed in [configuration.md](configuration.md).
- Use the Dockerfile's default command. It runs `alembic upgrade head` before starting Uvicorn.
- Set the health check to `/healthz`. A stopped scheduler or delivery thread makes it return 503.
- Run exactly one service instance and one Uvicorn process. Do not use `--workers`, replicas, or a separate worker service.
- Uvicorn gives active requests and SSE streams five seconds to drain, then signals the background threads to stop. The scheduler skips remaining scoreboard dates after the current request finishes. Disk-backed Render services have a fixed platform shutdown allowance; see [Render shutdown behavior](https://render.com/docs/deploys#graceful-shutdown). Interrupted alert attempts are marked failed on restart rather than resent.

Only files under `/var/data` survive deploys. Render disks cannot be shared across services, and disk-backed deploys briefly interrupt service. The browser reconnects its update stream after restart.

## Fresh SQLite Cutover

This branch deliberately starts fresh; it does not import or upgrade the old Postgres database.

1. Stop the old background worker before starting this backend, preventing duplicate alerts.
2. Add the persistent disk and replace the backend's `DATABASE_URL` with the SQLite URL above.
3. Remove obsolete `POSTGRES_*`, `NEON_*`, `LIVE_UPDATE_API_URL`, and `LIVE_UPDATE_SECRET` settings.
4. Deploy the backend. Its fresh schema, competition catalogs, and bootstrap admin are created automatically. Fresh databases enable all supported competitions; disable unwanted leagues in Admin.
5. Deploy the frontend with `VITE_API_BASE_URL` pointing at this backend.
6. Sign in again, recreate follows and preferences, and resubscribe notification devices.
7. Retire the old worker and database after verifying the new service. This code does not delete the remote database.

## Frontend

Build `apps/web` with Node.js 24:

```sh
npm ci --include=optional
VITE_API_BASE_URL=https://your-backend.example npm run build
```

Publish `dist` and configure SPA fallback for nested routes.

## Backups and Recovery

At startup and each six-hour catalog cycle, the backend creates a snapshot if that UTC day's backup is missing. It keeps the latest seven snapshots in `/var/data/backups`. Snapshots use SQLite's online backup API, include committed WAL writes, and pass an integrity check before publication. Backup failures are logged and do not block game synchronization.

Take an additional snapshot before a significant change:

```sh
/opt/venv/bin/python -m app.db.backup /var/data/backups/before-change.db
```

Download snapshots to storage outside the service's disk. Local snapshots protect against application mistakes; they do not protect against losing the entire volume. Snapshots contain user and authentication data and must stay private.

To restore, stop the backend, move the current database and any matching `-wal`/`-shm` files aside, and copy the chosen snapshot to the configured database path. Restart the backend and verify sign-in, follows, and alert history. Never copy only the live `.db` file as a backup while the backend is running.

## Verification

- Confirm `/healthz`, `/docs`, Games, Teams, sign-in, and follows.
- Confirm scheduler and delivery loops start once and Admin reports their schedule.
- Verify an enabled league ingests games and a committed change reaches `/updates/games`.
- Verify a test alert through the intended email and push channels.
- Check that a daily backup exists and can be opened with `PRAGMA integrity_check`.
- Restart the service and confirm persisted users and follows remain.

## League preference cutover

Deploy the frontend and backend together for the league-based alert preference API. Backend startup applies `0002_league_preferences`, which replaces only the user alert preference table and intentionally resets sport-wide settings to built-in league defaults. Users, authentication, follows, delivery settings, history, and game overrides remain intact. Explicit game overrides survive; inherited fields use the league settings. Downgrading this revision also clears preferences. Take an online backup before deployment; no full database reset is needed.
