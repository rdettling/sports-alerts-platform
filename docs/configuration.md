# Configuration

This repo uses strict environment loading. Missing required values fail fast at startup.

The local stack expects a single `.env` at the repo root.

## Minimal Local `.env`

```env
POSTGRES_USER=sports
POSTGRES_PASSWORD=sports
POSTGRES_DB=sports_alerts
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://sports:sports@db:5432/sports_alerts

JWT_SECRET_KEY=replace-with-long-random-string
WEB_BASE_URL=http://localhost:5173
CORS_ALLOW_ORIGINS=http://localhost:5173

ODDS_API_KEY=replace-with-the-odds-api-key
ODDS_ENABLED=false
CATALOG_SYNC_INTERVAL_SECONDS=43200

RESEND_API_KEY=replace-with-resend-api-key
DELIVERY_MODE=log
VAPID_PUBLIC_KEY=replace-with-public-vapid-key
VAPID_PRIVATE_KEY=replace-with-private-vapid-key
VAPID_SUBJECT=mailto:you@example.com

VITE_API_BASE_URL=http://localhost:8000

NEON_API_KEY=
NEON_PROJECT_ID=
NEON_ORG_ID=
NEON_DASHBOARD_URL=
```

Optional local overrides you may want to add:

```env
FROM_EMAIL=alerts@example.com
ODDS_PREGAME_WINDOW_HOURS=24
SCHEDULER_TICK_SECONDS=15
BOOTSTRAP_ADMIN_EMAIL=you@example.com
```

## API Config

The API service reads auth, app, delivery, and admin bootstrap settings.

Common values:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `WEB_BASE_URL`
- `CORS_ALLOW_ORIGINS`
- `RESEND_API_KEY`
- `DELIVERY_MODE`
- `FROM_EMAIL`
- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`
- `VAPID_SUBJECT`
- `BOOTSTRAP_ADMIN_EMAIL`

Notes:

- `BOOTSTRAP_ADMIN_EMAIL` defaults to `ryandettling1@gmail.com` in code if not overridden.
- `DELIVERY_MODE` supports `live` and `log`.
- The API needs both VAPID keys so it can report whether Push is available and return the public key to authenticated browsers.
- The VAPID private key remains server-only. `VAPID_SUBJECT` must be an HTTPS URL or `mailto:` contact.
- Magic-link behavior is configurable through `MAGIC_LINK_*` settings if the defaults are not suitable.

## Worker Config

The worker reads ingest cadence and odds settings.

Common values:

- `DATABASE_URL`
- `CATALOG_SYNC_INTERVAL_SECONDS`
- `SCHEDULER_TICK_SECONDS`
- `ODDS_ENABLED`
- `ODDS_API_KEY`
- `ODDS_PREGAME_WINDOW_HOURS`
- `DELIVERY_MODE`
- `VAPID_PRIVATE_KEY`
- `VAPID_SUBJECT`

Notes:

- `ODDS_API_KEY` is still required by settings validation even when `ODDS_ENABLED=false`.
- League-specific live cadences and odds provider sport keys are stable values in the league registry, not environment settings.
- The worker always handles schedule ingest and alert evaluation; `ODDS_ENABLED=false` only disables odds fetches.

## Frontend Config

The frontend currently needs one required env var:

- `VITE_API_BASE_URL`

Point it at the API origin the browser should call, for example `http://localhost:8000` locally.

## Optional Neon Integration

These values power the admin DB stats view when present:

- `NEON_API_KEY`
- `NEON_PROJECT_ID`
- `NEON_ORG_ID`
- `NEON_DASHBOARD_URL`

If they are absent, the app still runs; the admin UI just shows Neon data as unavailable.

## Secrets And Defaults

- Do not commit real secrets.
- Use local placeholders when a value is required structurally but not used in your current mode.
- Keep local and deployed secrets separate.
- For local development, `DELIVERY_MODE=log` simulates both email and Push delivery. Browser subscription still requires a valid VAPID key pair.
