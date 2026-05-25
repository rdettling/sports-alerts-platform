# Environment Variables

This repo uses strict env loading: if a required variable is missing, startup fails.

## Minimal required `.env`

Keep one `.env` at repo root with only required variables that do not have safe code defaults:

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
# Local default: keep odds disabled to avoid spending API calls
ODDS_ENABLED=false
ODDS_REFRESH_SECONDS=21600
NBA_LIVE_SYNC_INTERVAL_SECONDS=120
MLB_LIVE_SYNC_INTERVAL_SECONDS=300
ODDS_API_SPORT_KEY_NBA=basketball_nba
ODDS_API_SPORT_KEY_MLB=baseball_mlb
ODDS_PREGAME_WINDOW_HOURS=24
DELIVERY_ACTIVE_BACKOFF_SECONDS=120
DELIVERY_EMPTY_BACKOFF_SECONDS=900
DELIVERY_LIVE_FAST_BACKOFF_SECONDS=60
DELIVERY_LIVE_FAST_WINDOW_SECONDS=600
CLEANUP_INTERVAL_SECONDS=21600

RESEND_API_KEY=replace-with-resend-api-key
DELIVERY_MODE=email

VITE_API_BASE_URL=http://localhost:8000

# Optional: Neon DB usage in Admin > DB Stats tab
NEON_API_KEY=replace-with-neon-api-key
NEON_PROJECT_ID=solitary-resonance-98873129
NEON_ORG_ID=org-empty-paper-73359802
NEON_DASHBOARD_URL=https://console.neon.tech/app/projects/solitary-resonance-98873129
```

## Notes

- `ODDS_ENABLED=false` is recommended for local development to avoid spending odds API calls.
- `ODDS_REFRESH_SECONDS=21600` (6 hours) keeps odds refresh coarse outside urgent windows.
- Worker sync defaults: shared catalog `12h`; NBA live `120s`; MLB live `300s`.
- Live sync updates scores/status only; odds refresh is handled by catalog sync pregame snapshots.
- `TELEMETRY_RAW_EVENTS_ENABLED=false` keeps hourly rollups but skips per-call raw event writes.
- `ODDS_API_KEY` is still required by strict settings even when odds are disabled. Use a placeholder value if disabled.
- `DELIVERY_MODE=email` requires valid `RESEND_API_KEY` and verified sender (`FROM_EMAIL`).
  API uses the same delivery config for magic-link emails.
- Neon DB stats are shown only when `NEON_API_KEY` and `NEON_PROJECT_ID` are set.

## Service mapping

- API service needs API/auth/DB/cors/odds variables, plus delivery and magic-link settings.
- Worker service needs DB/provider/odds/delivery/polling variables.
- Frontend service needs `VITE_API_BASE_URL`.

## Secrets policy

- Never commit secrets.
- Keep real values only in local `.env` and Render env settings.
- Use different secrets for local and deployed environments.
