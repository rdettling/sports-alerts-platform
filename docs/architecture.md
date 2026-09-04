# Architecture

## Services

- **Web** (`apps/web`): React + Vite UI for public games and teams plus authenticated alerts and admin-only operations views
- **API** (`services/backend/app`): FastAPI service for auth, reads/writes, admin endpoints, startup seeding, and delivery helpers
- **Worker** (`services/backend/app/worker`): continuous schedule sync, odds snapshots, alert evaluation, and delivery execution
- **Postgres**: system of record for users, follows, games, odds snapshots, alert configuration, sent alerts, and lightweight ops state

## Runtime Shape

The web app talks only to the API. The API and worker both read and write the same Postgres database. After a changed sync commits, the worker also sends a small authenticated notification to the API so connected Games screens can refresh without polling the database continuously.

At startup, the API:

- seeds teams if missing
- ensures competition runtime rows exist
- ensures a bootstrap admin user exists for the configured email

The single worker process runs continuously with an in-memory schedule and manages:

- catalog sync across enabled competitions
- narrower live sync loops by competition
- optional pregame odds snapshots
- alert evaluation and delivery

## Current User-Facing Surfaces

The dashboard contains four sections:

- `Games`
- `Teams`
- `Alerts`
- `Admin` for users with `role=admin`

Games and Teams are public. Follow actions use progressive sign-in, and authenticated users can filter Games to their direct and team-derived follows.

Current supported competitions:

- `NBA`
- `WNBA`
- `NFL`
- `FBS`
- `MLB`
- `MLS`
- `LA_LIGA`
- `PREMIER_LEAGUE`
- `WORLD_CUP`

Competition availability has three independent layers:

- **Supported** competitions have code-owned profiles and remain manageable in Admin.
- **Active** competitions have `competition_settings.is_enabled = true`; only these competitions are polled by workers or exposed on user-facing screens and APIs.
- **Hidden** competitions are active globally but excluded from one signed-in user's Games and Teams views through `users.hidden_competitions`.

Changing a competition to inactive preserves its games, teams, follows, alerts, and user visibility preferences. Reactivating it restores that state. A fresh database activates the current supported catalog, while profiles added to an initialized database start inactive until an admin activates them.

Each supported competition has one code-owned profile containing its sport, provider identifiers, live cadence, display metadata, and any competition-specific alert restriction. Alert preferences are sport-wide; a competition profile determines which of that sport's alert types can apply to its games. La Liga and the Premier League omit extra-time and penalty alerts because their competition matches cannot enter those states. Presentation such as football season context or World Cup stage labels remains explicit. NFL preseason games are ingested without odds; regular-season and postseason games use the standard NFL moneyline feed. FBS uses ESPN's FBS group and the NCAAF odds feed; schedule opponents outside FBS are discovered during ingest so those games remain mappable.

## Main API Areas

The API is split into a small set of route groups:

- `/auth` — email sign-in start, link/code verification, auth warmup, current user
- `/games` — self-contained game feed with embedded participants, competition, status, finals filters, and current moneyline odds
- `/teams` — active team catalog
- `/follows` — team follows and effective game follows
- `/alert-preferences` — sport defaults and game-level overrides
- `/alerts` — alert history and the admin test-alert tool
- `/notification-settings` and `/push-subscriptions` — global delivery choice and browser subscriptions
- `/competitions` — active competition metadata for the UI
- `/ops` — admin-only alert activity, DB stats, and competition runtime controls
- `/updates/games` — public SSE notifications containing no game or user data
- `/internal/updates/games` — authenticated worker publish endpoint
- `/healthz` — health check

## Core Data Model

Main persisted tables:

- `users`
- `email_login_tokens`
- `teams`
- `competition_settings`
- `competition_teams`
- `games`
- `game_odds_current`
- `game_odds_outcomes_current`
- `user_team_follows`
- `user_game_follows`
- `user_game_unfollows`
- `user_alert_preferences`
- `user_game_alert_overrides`
- `alerts`
- `alert_deliveries`
- `push_subscriptions`

Notable modeling decisions:

- Teams are canonical provider entities, including incidental opponents needed to render games; `competition_teams` contains only browseable and followable competition members
- FBS conference names come from the code-owned team catalog and are exposed as a secondary UI facet, not stored as standalone competitions or database state
- Games retain their competition and can carry live/final state, scores, context labels, and odds associations
- A team follow applies to that team's games in every active competition, with explicit game unfollows stored separately
- Alert preference persistence stores sport-wide per-field differences from canonical defaults; competition profiles restrict which rules apply to each game
- Alerts are deduped events; channel-specific attempts and outcomes are stored as alert deliveries

## Key Flows

### Auth

1. User requests a sign-in email
2. API creates one `email_login_tokens` challenge containing hashes for a magic link and six-digit code
3. API sends both credentials through the configured delivery mode
4. Using either credential consumes the shared challenge, creates the user if needed, and returns a JWT
5. Installed Home Screen apps use the code so authentication completes inside their isolated browser context

### Game Sync

1. Worker fetches provider schedule/state for enabled competitions
2. Worker maps provider team IDs to the API-seeded catalog, stores non-FBS opponents from FBS schedules without granting FBS membership, and upserts games into Postgres
3. Worker snapshots odds for eligible pregame windows when enabled
4. After a changed transaction commits, the worker sends a best-effort notification to the API
5. The API invalidates its dashboard feed cache before broadcasting an in-memory SSE event. Visible Games screens batch events for one second and space event-driven reads at least two seconds apart, retaining one pending refresh if a request is already running
6. Opening/reconnecting the stream and returning to a visible, online Games screen trigger a catch-up read. Hidden/offline screens close SSE and pause refresh timers
7. After each completed request, live feeds use a 60-second fallback. Quiet feeds (empty, final-only, or scheduled-only) wait 30 minutes or until the earliest future scheduled start, whichever is sooner. A past scheduled start does not keep a quiet feed polling every minute. Before any successful load, failures recover on a 60-second fallback; later failures use the last known feed. No failure creates an immediate retry loop.

The quiet fallback allows gaps longer than Neon’s default five-minute inactivity timeout. SSE and its keep-alives do not query Postgres. Worker activity, other viewers, and reconnects can still keep the database awake. Missing an event during a quiet period can delay recovery until the next scheduled check (up to 30 minutes); normal SSE updates and foreground/reconnect catch-up remain prompt.

The API caches only the public dashboard request (`include_finals=true`, `limit=500`, no status/competition filters) for 30 seconds. Concurrent misses share one fill; cached response models retain no ORM entities, database sessions, or connections. Cache hits do not extend expiry. An invalidation during a fill discards that result and reloads using a new session. Competition enable/disable commits also invalidate the cache. Other game queries read the database directly, and all game responses use `Cache-Control: no-store` to prevent browser/CDN caching.

Worker notifications retry once after 250 milliseconds for network failures, timeouts, or HTTP 5xx responses, using a two-second HTTP timeout per attempt. HTTP 4xx responses are not retried. Notification failure never retries or fails the committed ingest transaction; repeated failure logs remain suppressed until recovery.

### Alert Evaluation

1. Worker loads effective followers and alert settings for touched games
2. Worker evaluates competition-appropriate alert types
3. Worker writes a deduplicated `alerts` event and channel-specific Email and/or Push `alert_deliveries` rows
4. Email delivery executes through log mode or live Resend mode
5. Web reads alert history through `/alerts/history`

### Admin / Ops

Admin-only routes expose:

- alert and delivery activity
- DB health views
- Neon usage when configured
- competition enable/disable controls
- test tools

Admin test alerts use transient sample objects to exercise the real Email and Push delivery paths. They return channel outcomes to the Tools view without entering game, alert history, or activity tables.

## Database Activity Observability

Both runtime processes aggregate existing SQLAlchemy connection, statement, transaction, and error events in memory. Every five minutes, nonempty `Database usage` summaries identify API route templates, worker scans/jobs, cache use, UTC activity minutes, and the deployed revision. A pure ASGI context middleware attributes API calls without buffering SSE. The logger never queries Postgres or retains a DB session. See the [runbook](runbook.md#reviewing-database-awake-time-and-waste) for the Neon snapshot and Render summary commands; observed activity is not a substitute for Neon’s actual awake-time counters.

## Design Constraints

- The worker is separate so ingest and delivery do not block request/response traffic
- Scheduler state is process-local; worker logs are the source of truth for job timing and failures
- SSE fanout and the dashboard feed cache are process-local and assume one API process on one instance; multiple processes or instances require shared broadcasting and cache invalidation
- Odds are persisted and read from the DB instead of fetched from the browser path
- RBAC is DB-backed through `users.role`
- Settings are strict enough that missing required env values fail early
- Sports-domain data is operationally disposable compared with user identity/auth data
