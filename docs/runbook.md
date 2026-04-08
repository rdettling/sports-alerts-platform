# Runbook (Troubleshooting)

## API unreachable from frontend

Symptoms:

- Login/register fails with "Unable to reach API..."

Checks:

1. Verify `VITE_API_BASE_URL` points to the correct API domain.
2. Verify API service is healthy (`/healthz`).
3. Verify `CORS_ALLOW_ORIGINS` includes frontend origin.
4. Check `make logs SERVICE=api` for startup/config errors.

## Frontend route 404 on hard refresh

Symptoms:

- Direct refresh on nested route returns `Not Found`.

Fix:

- Ensure static hosting rewrite/fallback is configured for SPA routing on your frontend host.

## Odds not showing

Checks:

1. Confirm `ODDS_ENABLED=true`.
2. Confirm `ODDS_API_KEY` is valid (no 401s in worker logs).
3. Confirm refresh interval: `ODDS_REFRESH_SECONDS` may delay updates.
4. Check worker logs for odds fetch failures.

If intentionally disabled:

- `ODDS_ENABLED=false` means game rows can show no odds by design.

## Worker starts but no alerts are sent

Checks:

1. Confirm users follow teams/games.
2. Confirm alert preferences are enabled.
3. Confirm worker logs show ingest cycles and alert evaluation.
4. For email delivery:
   - `DELIVERY_MODE=email`
   - valid `RESEND_API_KEY`
   - verified `FROM_EMAIL`

## Bad local state / stale data

Use carefully:

- `make down` (stop, keep DB)
- `make rebuild` (rebuild and restart)
- `make reset` (wipe DB volume)

`make reset` deletes local DB data and requires re-registering users.

## Strict env startup failures

Symptoms:

- startup validation errors for missing env vars

Fix:

- Ensure all required variables in `docs/environment-variables.md` exist in `.env` (local) or service env settings (Render).
