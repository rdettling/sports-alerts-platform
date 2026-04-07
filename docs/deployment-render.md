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

- `DATABASE_URL=postgresql+psycopg://...?...`
- `JWT_SECRET_KEY=...`
- `CORS_ALLOW_ORIGINS=https://<frontend>.onrender.com`

## Worker Service Settings

- Root Directory: `.`
- Docker Build Context Directory: `.`
- Dockerfile Path: `services/worker/Dockerfile`
- Docker Command: `uv run python -m worker.main`
- Pre-Deploy Command: blank

Required env vars:

- `DATABASE_URL=postgresql+psycopg://...?...`
- `NBA_PROVIDER=espn`
- `DELIVERY_MODE=log` (or `email`)

When `DELIVERY_MODE=email`, also set:

- `RESEND_API_KEY=<resend-api-key>`
- `FROM_EMAIL=<verified-sender@your-domain>`

## Frontend Static Site Settings

- Root Directory: `apps/web`
- Build Command: `npm ci --include=optional && npm run build`
- Publish Directory: `dist`

Required env var:

- `VITE_API_BASE_URL=https://<api>.onrender.com`

## Smoke Test

- API `.../healthz` returns 200
- Register/login works in frontend
- Teams/games load
- Worker logs show ingest cycles
