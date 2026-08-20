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

## Email Sign-In Issues

Checks:

1. Confirm the API is reachable and healthy
2. Confirm `WEB_BASE_URL` points at the frontend origin users should land on
3. Confirm delivery mode is intentional:
   - `DELIVERY_MODE=log` for local inspection
   - `DELIVERY_MODE=live` for real delivery
4. For live email, confirm `RESEND_API_KEY` and `FROM_EMAIL` are valid
5. Check API logs for sign-in email rate limiting or delivery warnings
6. For an installed iPhone or iPad Home Screen app, enter the emailed code in the app; opening the link authenticates Safari instead

## Odds Not Showing

Checks:

1. Confirm `ODDS_API_KEY` is nonblank and valid if you expect odds
2. Confirm the worker is running
3. Check worker logs for odds fetch failures during catalog sync

Expected behavior:

- when `ODDS_API_KEY` is blank, games still load but odds values can be empty

## Worker Running But Alerts Not Arriving

Checks:

1. Confirm the worker is running and logging sync activity
2. Confirm a relevant league is enabled in `league_settings`
3. Confirm users follow teams or games that should produce alert candidates
4. Confirm the resolved league or per-game settings have the alert type enabled; per-game fields inherit league values until explicitly changed
5. For real delivery, confirm `DELIVERY_MODE=live`
6. For email failures, confirm the Resend settings
7. For Push failures, confirm `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT`, then inspect the aggregate `provider_data`
8. Inspect `alerts`, `alert_deliveries`, and worker logs for dedupe or delivery failures

## Push Not Available Or Not Arriving

Checks:

1. Confirm the Alerts page reports Push as configured
2. Confirm notification permission is granted for the site
3. On iPhone or iPad, confirm the site was added to the Home Screen and opened from there
4. Confirm the current device is subscribed on the Alerts page
5. Confirm the user selected Push or Both
6. Check the push delivery row; expired endpoints (`404` or `410`) are removed automatically

Push has no email fallback. A Push-only alert remains failed if no active device accepts it.

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
cd services/backend
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
- use [configuration.md](configuration.md) as the source of truth
