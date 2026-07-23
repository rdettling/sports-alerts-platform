# Architecture

## Services

- **Web** (`apps/web`): React + Vite UI for auth, games, following, alerts, and admin-only runtime views
- **API** (`services/api`): FastAPI service for auth, reads/writes, admin endpoints, startup seeding, and delivery helpers
- **Worker** (`services/worker`): continuous schedule sync, odds snapshots, alert evaluation, and delivery execution
- **Postgres**: system of record for users, follows, games, odds snapshots, alert configuration, sent alerts, and lightweight ops state

## Runtime Shape

The web app talks only to the API. The API and worker both read and write the same Postgres database.

At startup, the API:

- seeds teams if missing
- ensures league runtime rows exist
- ensures a bootstrap admin user exists for the configured email

The worker runs continuously and manages:

- catalog sync across enabled leagues
- narrower live sync loops by league
- optional pregame odds snapshots
- alert evaluation and delivery

## Current User-Facing Surfaces

The dashboard contains four sections:

- `Games`
- `Following`
- `Alerts`
- `Admin` for users with `role=admin`

Current supported leagues:

- `NBA`
- `MLB`
- `MLS`
- `WORLD_CUP`

League runtime is controlled by DB-backed `league_settings`, so disabled leagues disappear from user-facing reads and worker scope without a code change.

Each supported league has one code-owned profile containing its sport, provider identifiers, live cadence, and display metadata. Alert availability and shared game behavior are selected by sport: basketball, baseball, or soccer. User preferences remain league-specific, and presentation such as World Cup stage labels remains explicit.

## Main API Areas

The API is split into a small set of route groups:

- `/auth` — magic-link start/verify, auth warmup, current user
- `/games` — game feed with league/status/finals/odds options
- `/teams` — active team catalog
- `/follows` — team follows and effective game follows
- `/alert-preferences` — league defaults and game-level overrides
- `/alerts` — alert history and admin test-email tools
- `/leagues` — active league metadata for the UI
- `/ops` — admin-only telemetry, DB stats, and league runtime controls
- `/healthz` — health check

## Core Data Model

Main persisted tables:

- `users`
- `email_login_tokens`
- `teams`
- `league_settings`
- `games`
- `game_odds_current`
- `game_odds_outcomes_current`
- `user_team_follows`
- `user_game_follows`
- `user_game_unfollows`
- `user_alert_defaults`
- `user_game_alert_overrides`
- `sent_alerts`
- `api_call_rollups_hourly`
- `worker_jobs`

Notable modeling decisions:

- Games are retained as normalized rows and can carry live/final state, scores, context labels, and odds associations
- Team follows can imply effective game follows, with explicit game unfollows stored separately
- Alert settings exist at two levels: league defaults and per-game overrides
- Sent alerts are deduped and also serve as delivery history

## Key Flows

### Auth

1. User requests a magic link
2. API creates an `email_login_tokens` row
3. API sends the link through the configured delivery mode
4. Verify flow consumes the token, creates the user if needed, and returns a JWT

### Game Sync

1. Worker fetches provider schedule/state for enabled leagues
2. Worker upserts teams and games into Postgres
3. Worker snapshots odds for eligible pregame windows when enabled
4. Web reads the DB-backed game state through `/games`

### Alert Evaluation

1. Worker loads effective followers and alert settings for touched games
2. Worker evaluates league-appropriate alert types
3. Worker writes `sent_alerts` rows with dedupe keys
4. Delivery executes through log mode or email mode
5. Web reads alert history through `/alerts/history`

### Admin / Ops

Admin-only routes expose:

- provider usage rollups
- ingest and DB health views
- Neon usage when configured
- league enable/disable controls
- test tools

## Design Constraints

- The worker is separate so ingest and delivery do not block request/response traffic
- Odds are persisted and read from the DB instead of fetched from the browser path
- RBAC is DB-backed through `users.role`
- Settings are strict enough that missing required env values fail early
- Sports-domain data is operationally disposable compared with user identity/auth data
