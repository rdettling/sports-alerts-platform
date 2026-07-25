# Runbook

## API Unreachable From The Frontend

Symptoms:

- sign-in fails because the browser cannot reach the API
- dashboard data requests fail immediately

Checks:

1. Confirm `VITE_API_BASE_URL` points at the correct API origin
2. Confirm `GET /healthz` is healthy
3. Confirm `CORS_ALLOW_ORIGINS` includes the frontend origin
4. Check `make logs SERVICE=api` for startup or config failures

## Frontend Route 404 On Hard Refresh

Symptoms:

- direct browser refresh on a nested route returns `404`

Fix:

- configure SPA fallback / rewrites on the frontend host

## Magic-Link Auth Issues

Checks:

1. Confirm the API is reachable and healthy
2. Confirm `WEB_BASE_URL` points at the frontend origin users should land on
3. Confirm delivery mode is intentional:
   - `DELIVERY_MODE=log` for local inspection
   - `DELIVERY_MODE=live` for real delivery
4. For live mode, confirm `RESEND_API_KEY` and `FROM_EMAIL` are valid
5. Check API logs for magic-link rate limiting or delivery warnings

## Odds Not Showing

Checks:

1. Confirm `ODDS_ENABLED=true` if you expect odds
2. Confirm `ODDS_API_KEY` is valid
3. Confirm the worker is running
4. Check worker logs for odds fetch failures during catalog sync

Expected behavior:

- when `ODDS_ENABLED=false`, games still load but odds values can be empty

## Worker Running But Alerts Not Arriving

Checks:

1. Confirm the worker is running and logging sync activity
2. Confirm a relevant league is enabled in `league_settings`
3. Confirm users follow teams or games that should produce alert candidates
4. Confirm league defaults or game overrides have the alert type enabled
5. For real email delivery, confirm `DELIVERY_MODE=live` and valid Resend settings
6. Inspect `alerts`, `alert_deliveries`, and worker logs for dedupe or delivery failures

## Bad Local State

Escalation path:

1. `make down`
2. `make up`
3. `make rebuild`
4. `make reset`

`make reset` deletes local DB data, including local sign-in/session state in the database.

## Sports Data Reset And Reseed

Use this when you want to keep the repo shape but clear sports-domain state.

1. Stop or pause the worker
2. Run:

```sh
cd services/api
uv run alembic upgrade head
uv run python scripts/reset_sports_data.py --yes
```

3. Restart API and worker
4. Confirm teams were reseeded and ingest resumes cleanly
5. Confirm user identity/auth data still looks correct before resuming normal use

## Strict Env Startup Failures

Symptoms:

- API or worker exits during startup with settings validation errors

Fix:

- make sure required values exist in `.env` or your deployed service environment
- use [configuration.md](/Users/rdettling/Library/Mobile Documents/com~apple~CloudDocs/Code/projects/sports-alerts-platform/docs/configuration.md) as the source of truth
