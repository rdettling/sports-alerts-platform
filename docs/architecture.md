# Architecture

## Runtime Components

- `web` (React/Vite static frontend)
- `api` (FastAPI + Alembic + SQLAlchemy)
- `worker` (polling + rule evaluation + delivery)
- `postgres` (source of truth)

## Data Flow

1. User actions go from `web` to `api` (auth, follows, preferences).
2. `worker` polls NBA data provider and upserts `games`.
3. `worker` evaluates alert rules per user and writes `sent_alerts`.
4. `web` reads alert history from `api`.

## Key Design Choices

- API and worker are separate services.
- Deduplication is enforced in `sent_alerts.dedupe_key`.
- V1 delivery defaults to `DELIVERY_MODE=log`.
- Environment variables configure DB/auth/provider polling behavior.
