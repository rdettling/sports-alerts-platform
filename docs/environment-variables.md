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
ODDS_ENABLED=true
ODDS_REFRESH_SECONDS=21600
INGEST_LIVE_INTERVAL_SECONDS=120
INGEST_PREGAME_HOT_INTERVAL_SECONDS=900
INGEST_PREGAME_COLD_INTERVAL_SECONDS=3600
INGEST_OFF_INTERVAL_SECONDS=43200
INGEST_PREGAME_HOT_WINDOW_MINUTES=90
INGEST_PREGAME_COLD_WINDOW_HOURS=24
INGEST_HEARTBEAT_SECONDS=3600
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

- `ODDS_ENABLED=true` keeps odds updates active.
- `ODDS_REFRESH_SECONDS=21600` (6 hours) keeps odds refresh coarse outside urgent windows.
- Worker polling defaults to low-compute cadence: live `120s`, pregame-hot `15m`, pregame-cold `60m`, off `12h`.
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
