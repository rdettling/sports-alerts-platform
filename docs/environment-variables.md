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
```

## Render: API

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `CORS_ALLOW_ORIGINS`

Optional:

- `JWT_ALGORITHM`
- `JWT_EXPIRE_MINUTES`

## Render: Worker

- `DATABASE_URL`

Recommended:

- `NBA_PROVIDER=espn`
- `DELIVERY_MODE=log`
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
