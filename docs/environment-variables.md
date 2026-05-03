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
ODDS_ENABLED=false
INGEST_LIVE_INTERVAL_SECONDS=45
INGEST_PREGAME_HOT_INTERVAL_SECONDS=300
INGEST_PREGAME_COLD_INTERVAL_SECONDS=1800
INGEST_OFF_INTERVAL_SECONDS=14400
INGEST_PREGAME_HOT_WINDOW_MINUTES=90
INGEST_PREGAME_COLD_WINDOW_HOURS=24
INGEST_HEARTBEAT_SECONDS=3600

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

- `ODDS_ENABLED=false` disables odds API fetches in worker.
- `ODDS_REFRESH_SECONDS` defaults to `7200` (2 hours).
- Worker polling defaults to low-compute cadence: live `45s`, pregame-hot `5m`, pregame-cold `30m`, off `4h`.
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
