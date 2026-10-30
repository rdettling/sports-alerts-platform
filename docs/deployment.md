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

## Schema Changes and Data Preservation

Normal deploys reuse the persistent SQLite database. The startup command applies pending Alembic revisions, then reconciles the team catalog in place. Already-applied migrations are not rerun. Deploys do not reset accounts, follows, preferences, or notification subscriptions.

Use small forward migrations to reach the current schema. Keep applied revisions and support only the latest schema in application code; no runtime compatibility layer is needed.

Preserve accounts, authentication, personal settings, follows, subscriptions, and the team identities they reference. Catalog changes may update team details and memberships without deleting team rows or follows. Games, odds, standings, and derived alert history may be rebuilt for a specific change when that avoids complicated backfills. Preserve or remap active game follows, unfollows, and per-game overrides before replacing referenced games; ordinary game retention still expires old game-specific state.

Before a production schema change, take an online snapshot and copy it off the service's disk. If a change rebuilds sports data, document exactly which records will be cleared and how personal references survive. Use the existing backend to repopulate the affected sports data. A whole-database reset requires explicit approval to lose personal data; it is not a routine deployment step.

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
