# Runbook (Troubleshooting)

## API unreachable from frontend

Symptoms:

- Magic-link login fails with "Unable to reach API..."

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
3. Check worker logs for odds fetch failures during catalog sync.

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

`make reset` deletes local DB data and requires signing in again with a new magic link.

## Full sports data reset + reseed (identity migration)

Use this during a maintenance window when you want a clean sports-domain reset.

1. Pause worker and hold API traffic briefly.
2. Run migrations:
`cd services/api && uv run alembic upgrade head`
3. Reset sports-domain tables and reseed teams:
`cd services/api && uv run python scripts/reset_sports_data.py --yes`
4. Restart API and worker.
5. Verify worker logs do not show missing-team ingest skips.
6. Verify team mapping health:
`GET /ops/db/team-mapping-health?date=YYYYMMDD`
Expected: `ok=true` and empty `missing_team_ids` for MLB and NBA.

## Strict env startup failures

Symptoms:

- startup validation errors for missing env vars

Fix:

- Ensure all required variables in `docs/environment-variables.md` exist in `.env` (local) or service env settings (Render).
