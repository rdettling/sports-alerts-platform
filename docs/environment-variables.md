# Environment Variables

## Local minimum (`.env`)

```env
JWT_SECRET_KEY=replace-with-long-random-string
```

## Local optional

```env
VITE_API_BASE_URL=http://localhost:8000
DATABASE_URL=postgresql+psycopg://sports:sports@db:5432/sports_alerts
CORS_ALLOW_ORIGINS=http://localhost:5173
ODDS_API_KEY=your_the_odds_api_key
```

## Render: API

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `CORS_ALLOW_ORIGINS`

Optional:

- `JWT_ALGORITHM`
- `JWT_EXPIRE_MINUTES`
- `ODDS_API_REGIONS` (default `us`)
- `ODDS_API_MARKET` (default `h2h`)
- `ODDS_API_FORMAT` (default `american`)
- `ODDS_API_CACHE_SECONDS` (default `60`)

## Render: Worker

- `DATABASE_URL`
- `DELIVERY_MODE`

Recommended:

- `NBA_PROVIDER=espn`
- `DELIVERY_MODE=log` (or `email` when Resend is configured)
- `RESEND_API_KEY` (required when `DELIVERY_MODE=email`)
- `FROM_EMAIL` (verified sender address for Resend)
- `ODDS_API_KEY` (required to ingest odds into DB)
- `WORKER_POLL_INTERVAL_SECONDS`
- `WORKER_POLL_INTERVAL_LIVE_SECONDS`
- `WORKER_POLL_INTERVAL_SOON_SECONDS`
- `WORKER_POLL_INTERVAL_DAY_SECONDS`
- `WORKER_POLL_INTERVAL_IDLE_SECONDS`

## Render: Frontend

- `VITE_API_BASE_URL`

## Secret Handling Rules

- Never commit real secrets.
- Keep secrets in local `.env` and Render environment settings only.
- Use different `JWT_SECRET_KEY` values for local and deployed environments.
