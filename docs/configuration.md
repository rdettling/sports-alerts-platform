# Configuration

The local Docker stack reads one root `.env`. Unrelated keys are ignored. Missing required secrets fail at startup.

## Minimal Local `.env`

```env
JWT_SECRET_KEY=replace-with-long-random-string
WEB_BASE_URL=http://localhost:5173
CORS_ALLOW_ORIGINS=http://localhost:5173
RESEND_API_KEY=replace-with-resend-api-key
DELIVERY_MODE=log
ODDS_API_KEY=
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:you@example.com
VITE_API_BASE_URL=http://localhost:8000
```

Compose overrides the database URL to `sqlite:////var/data/sports-alerts.db` on its named persistent volume. Outside Docker, the default database is `~/.local/share/sports-alerts/sports-alerts.db`, outside the source checkout and cloud-synced folders. Only local, file-backed SQLite databases are supported.

## Backend

API, odds, email, and push settings live in `app/config.py`. Database location and connection setup live in `app/db/session.py`, so schema and backup commands do not require unrelated API secrets.

Required:

- `JWT_SECRET_KEY`: signs API sessions and hashes login codes.
- `WEB_BASE_URL`: frontend origin used in sign-in links.
- `CORS_ALLOW_ORIGINS`: comma-separated frontend origins.
- `RESEND_API_KEY`: required even in log mode; a placeholder is sufficient locally.

Database and identity:

- `DATABASE_URL`: SQLite file URL. Production must use a persistent disk path.
- `BOOTSTRAP_ADMIN_EMAIL`: administrator ensured on startup; defaults to the project owner's address. Blank disables bootstrap administration.
- `JWT_ALGORITHM`: defaults to `HS256`.
- `JWT_EXPIRE_MINUTES`: defaults to 86400.
- `MAGIC_LINK_TTL_MINUTES`: defaults to 15.
- `MAGIC_LINK_COOLDOWN_SECONDS`: defaults to 60.
- `MAGIC_LINK_MAX_REQUESTS_PER_HOUR`: defaults to 5.

Delivery:

- `DELIVERY_MODE`: `live` or `log`; defaults to `live`.
- `FROM_EMAIL`: defaults to `alerts@livegamealerts.com`.
- `RESEND_API_URL`: defaults to `https://api.resend.com/emails`.
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`: Web Push credentials. Keep the same keys across deploys to preserve browser subscriptions.

`ODDS_API_KEY` enables optional moneyline snapshots. Blank skips odds fetching. The daily credit cap is shared across competitions.

The scheduler and delivery dispatcher start with the API. They need no separate URL, shared internal secret, or worker service. Catalog sync runs every six hours, odds sweeps twice daily when needed, and live intervals come from competition profiles.

## Frontend

`VITE_API_BASE_URL` is required at build time and must point to the browser-accessible backend origin. Run a single backend process on one instance; game notifications and cache invalidation are in memory.
