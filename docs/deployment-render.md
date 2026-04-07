# Deployment (Render + Neon)

## Services

Create 3 Render services:

- `sports-alerts-platform-api` (Docker Web Service)
- `sports-alerts-platform-worker` (Docker Background Worker)
- `sports-alerts-platform-frontend` (Static Site)

Use Neon for managed Postgres.

## API Service Settings

- Root Directory: `.`
- Docker Build Context Directory: `.`
- Dockerfile Path: `services/api/Dockerfile`
- Docker Command: leave blank (uses Dockerfile CMD)
- Pre-Deploy Command: leave blank on free plan

Required env vars:

- Set all API variables listed in `docs/environment-variables.md` (API section equivalents).
- At minimum this includes: `APP_NAME`, `API_HOST`, `API_PORT`, `DATABASE_URL`,
  `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `CORS_ALLOW_ORIGINS`,
  `ODDS_API_KEY`, `ODDS_API_BASE_URL`, `ODDS_PROVIDER`, `ODDS_API_SPORT_KEY`,
  `ODDS_API_REGIONS`, `ODDS_API_MARKET`, `ODDS_API_FORMAT`,
  `ODDS_API_TIMEOUT_SECONDS`, `ODDS_API_CACHE_SECONDS`, `DEV_MODE`.

## Worker Service Settings

- Root Directory: `.`
- Docker Build Context Directory: `.`
- Dockerfile Path: `services/worker/Dockerfile`
- Docker Command: `uv run python -m worker.main`
- Pre-Deploy Command: blank

Required env vars:

- Set all Worker variables listed in `docs/environment-variables.md` (Worker section equivalents).
- This includes: `DATABASE_URL`, `NBA_PROVIDER`, `DELIVERY_MODE`, `FROM_EMAIL`,
  `RESEND_API_KEY`, `RESEND_API_URL`, `WORKER_POLL_INTERVAL_SECONDS`,
  `WORKER_POLL_INTERVAL_LIVE_SECONDS`, `WORKER_POLL_INTERVAL_SOON_SECONDS`,
  `WORKER_POLL_INTERVAL_DAY_SECONDS`, `WORKER_POLL_INTERVAL_IDLE_SECONDS`,
  `DEV_MODE`.

## Frontend Static Site Settings

- Root Directory: `apps/web`
- Build Command: `npm ci --include=optional && npm run build`
- Publish Directory: `dist`

Required env vars:

- `VITE_API_BASE_URL=https://<api>.onrender.com`
- `DEV_MODE=false` (recommended in production)

## Smoke Test

- API `.../healthz` returns 200
- Register/login works in frontend
- Teams/games load
- Worker logs show ingest cycles
