# Environment Variables

This repo uses strict env loading: if a required variable is missing, startup fails.

## Single local `.env` file

Keep one `.env` at repo root with all required variables:

```env
APP_NAME=sports-alerts-api
API_HOST=0.0.0.0
API_PORT=8000

POSTGRES_USER=sports
POSTGRES_PASSWORD=sports
POSTGRES_DB=sports_alerts
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://sports:sports@db:5432/sports_alerts

JWT_SECRET_KEY=replace-with-long-random-string
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
CORS_ALLOW_ORIGINS=http://localhost:5173

ODDS_API_KEY=replace-with-the-odds-api-key-or-placeholder
ODDS_API_BASE_URL=https://api.the-odds-api.com/v4/sports
ODDS_PROVIDER=the_odds_api
ODDS_API_SPORT_KEY=basketball_nba
ODDS_API_REGIONS=us
ODDS_API_MARKET=h2h
ODDS_API_FORMAT=american
ODDS_API_TIMEOUT_SECONDS=6
ODDS_API_CACHE_SECONDS=60
ODDS_ENABLED=false
ODDS_REFRESH_SECONDS=5400

DEV_MODE=false

NBA_PROVIDER=espn
DELIVERY_MODE=log
FROM_EMAIL=alerts@livegamealerts.com
RESEND_API_KEY=replace-with-resend-api-key
RESEND_API_URL=https://api.resend.com/emails

WORKER_POLL_INTERVAL_SECONDS=60
WORKER_POLL_INTERVAL_LIVE_SECONDS=30
WORKER_POLL_INTERVAL_SOON_SECONDS=120
WORKER_POLL_INTERVAL_DAY_SECONDS=300
WORKER_POLL_INTERVAL_IDLE_SECONDS=900

VITE_API_BASE_URL=http://localhost:8000
```

## Notes

- `ODDS_ENABLED=false` disables odds API fetches in worker.
- `ODDS_API_KEY` is still required by strict settings even when odds are disabled. Use a placeholder value if disabled.
- `DEV_MODE=true` enables:
  - API dev endpoint: `/alerts/dev/test-email`
  - frontend `Test` tab
- `DELIVERY_MODE=email` requires valid `RESEND_API_KEY` and verified sender (`FROM_EMAIL`).

## Service mapping

- API service needs API/auth/DB/cors/odds/dev variables.
- Worker service needs DB/provider/odds/delivery/polling variables.
- Frontend service needs `VITE_API_BASE_URL` and optional `DEV_MODE`.

## Secrets policy

- Never commit secrets.
- Keep real values only in local `.env` and Render env settings.
- Use different secrets for local and deployed environments.
