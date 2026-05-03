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

RESEND_API_KEY=replace-with-resend-api-key
DELIVERY_MODE=log

VITE_API_BASE_URL=http://localhost:8000
```

## Notes

- `ODDS_ENABLED=false` disables odds API fetches in worker.
- `ODDS_REFRESH_SECONDS` defaults to `7200` (2 hours).
- `TELEMETRY_RAW_EVENTS_ENABLED=false` keeps hourly rollups but skips per-call raw event writes.
- `ODDS_API_KEY` is still required by strict settings even when odds are disabled. Use a placeholder value if disabled.
- `DELIVERY_MODE=email` requires valid `RESEND_API_KEY` and verified sender (`FROM_EMAIL`).
  API uses the same delivery config for magic-link emails.

## Service mapping

- API service needs API/auth/DB/cors/odds variables, plus delivery and magic-link settings.
- Worker service needs DB/provider/odds/delivery/polling variables.
- Frontend service needs `VITE_API_BASE_URL`.

## Secrets policy

- Never commit secrets.
- Keep real values only in local `.env` and Render env settings.
- Use different secrets for local and deployed environments.
