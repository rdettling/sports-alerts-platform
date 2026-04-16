# Deployment (Render + Neon)

This app deploys as three Render services plus one Neon Postgres database.

Current production frontend domain: [https://livegamealerts.com](https://livegamealerts.com)

## Services

- `sports-alerts-platform-api` — Docker Web Service
- `sports-alerts-platform-worker` — Docker Background Worker
- `sports-alerts-platform-frontend` — Static Site

## 1) API Service (Docker Web Service)

- Root Directory: `.`
- Docker Build Context Directory: `.`
- Dockerfile Path: `services/api/Dockerfile`
- Docker Command: leave blank
- Pre-Deploy Command: leave blank

Set all required API env vars from `docs/environment-variables.md`.

Health checks:

- `GET /healthz` must return `200`
- `GET /docs` should load OpenAPI docs

## 2) Worker Service (Docker Background Worker)

- Root Directory: `.`
- Docker Build Context Directory: `.`
- Dockerfile Path: `services/worker/Dockerfile`
- Docker Command: `uv run python -m worker.main`
- Pre-Deploy Command: leave blank

Set all required worker env vars from `docs/environment-variables.md`.

Important behavior:

- If `ODDS_ENABLED=false`, worker still ingests games and evaluates alerts; only odds fetches are skipped.

## 3) Frontend Service (Static Site)

- Root Directory: `apps/web`
- Build Command: `npm ci --include=optional && npm run build`
- Publish Directory: `dist`

Required frontend env:

- `VITE_API_BASE_URL=https://<your-api-domain>`
- Optional: `DEV_MODE=false`

## 4) Neon Postgres

- Create database in Neon.
- Copy connection string into Render `DATABASE_URL` for API and worker.

## 5) Custom Domains

- Configure DNS at your registrar (for example Namecheap) using values from Render.
- Wait for DNS propagation, then verify in Render.
- Keep the Render default domain enabled until custom cert is active.

## Post-Deploy Smoke Test

1. Open frontend and request a magic-link sign-in.
2. Confirm games/following/alerts tabs load.
3. If signed in as an admin user (`users.role='admin'`), confirm the `Ops` tab loads.
4. Confirm API health endpoint is green.
5. Check worker logs for successful ingest cycles.
6. If using email delivery, trigger a dev test alert with `DEV_MODE=true` and verify delivery.
