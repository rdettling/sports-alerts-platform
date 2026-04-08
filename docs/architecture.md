# Architecture

## Services

- **Web** (`apps/web`): React UI for auth, games, following, and alerts.
- **API** (`services/api`): FastAPI HTTP service for auth, reads, follows, and preference updates.
- **Worker** (`services/worker`): background ingest + rule evaluation + delivery.
- **Postgres**: system of record for users, follows, games, preferences, odds, and sent alerts.

## High-Level Flow

1. User authenticates in web app.
2. Web reads/writes state through API.
3. Worker continuously ingests game/provider updates.
4. Worker evaluates enabled rules per user/game context.
5. Worker stores and delivers alert events.
6. Web reads alert history from API.

## Core Data Model

- `users`
- `teams`
- `games`
- `user_team_follows`
- `user_game_follows`
- `user_alert_preferences`
- `sent_alerts` (dedupe + delivery status)
- `ingest_runs` (worker cycle observability)
- `game_odds_current` (latest matched odds per game)

## Key Design Decisions

- Separate worker service avoids blocking request/response API paths.
- Rule evaluation is stateful and idempotent via dedupe keys.
- Odds are cached/persisted; UI reads from DB, not direct provider calls.
- Env config is strict: missing required vars fail fast at startup.
