# Environment Variables

This repo now uses **strict env loading**: no runtime defaults for required settings.
If a required variable is missing, API/worker/frontend startup fails.

## Single local `.env` contract

Keep all variables below in your local `.env`.

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

ODDS_API_KEY=replace-with-the-odds-api-key
ODDS_API_BASE_URL=https://api.the-odds-api.com/v4/sports
ODDS_PROVIDER=the_odds_api
ODDS_API_SPORT_KEY=basketball_nba
ODDS_API_REGIONS=us
ODDS_API_MARKET=h2h
ODDS_API_FORMAT=american
ODDS_API_TIMEOUT_SECONDS=6
ODDS_API_CACHE_SECONDS=60

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

## Usage notes

- `DEV_MODE` controls both:
  - API dev-only endpoints (for example `/alerts/dev/test-email`)
  - Frontend `Test` tab visibility
- `DELIVERY_MODE=email` requires valid `RESEND_API_KEY` and `FROM_EMAIL`.
- `ODDS_API_KEY` is required because odds ingestion is part of core game display.

## Render mapping

Set the same variables in Render service environment settings:

- API: API/JWT/CORS/odds/env flags/database vars
- Worker: database/provider/delivery/poll/odds/env flags
- Frontend: `VITE_API_BASE_URL` and `DEV_MODE` (if you want the test tab in non-local environments)

## Secret handling

- Never commit real secrets.
- Keep real values in local `.env` and Render environment settings only.
- Use different `JWT_SECRET_KEY` and `RESEND_API_KEY` values across local and deployed environments.
