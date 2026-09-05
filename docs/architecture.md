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

### Worker Scheduling

The single worker process runs continuously with an in-memory schedule and manages:

- one shared catalog cycle across enabled competitions
- narrower live sync loops by competition
- optional pregame odds snapshots
- alert evaluation and delivery

The worker reads enabled competitions at startup and on each scheduler iteration. When no job is due, it waits until the next scheduled job, capped at `CATALOG_SYNC_INTERVAL_SECONDS` (12 hours by default). With no enabled competitions, it waits one catalog interval before checking again. There is no separate hourly settings poll. Waits are interruptible on shutdown; kickoff scheduling, live polling, and job retries can all wake it sooner.

Catalog cycles are anchored to worker startup: one immediate cycle, then every `CATALOG_SYNC_INTERVAL_SECONDS`. Each cycle queues one attempt per enabled league and advances the shared clock without waiting for completion. Missed cycles are skipped rather than replayed. Successful catalog records have no independent timer; failed attempts retain a per-league retry deadline (30 seconds, exponentially increasing to one hour). The next regular cycle replaces outstanding catalog retries and resets their failure counts. Due live jobs take priority between catalog attempts, except that a league's startup catalog attempt precedes its first live read. Each league attempt uses a short planning read, closes that session for scoreboard and odds HTTP requests, then opens one write transaction. A failed startup catalog attempt does not block that league's live reads of existing games.

Admin league settings are saved immediately, but the sleeping worker discovers them on its next wake. Newly enabled leagues wait for the next shared catalog cycle, even if discovered earlier during live work, and may miss games or alerts for up to about 12 hours. Their existing live-job initialization can still monitor previously stored games. Disabled leagues are removed from the schedule before the next job is selected. Restarting the worker discovers current settings immediately and also reruns startup jobs.

## Current User-Facing Surfaces

The dashboard contains four sections:

- `Games`
- `Teams`
- `Alerts`
- `Admin` for users with `role=admin`: Leagues and Activity & tools (see [Admin / Ops](#admin--ops))

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
- `/internal/updates/games` — authenticated worker game-change endpoint
- `/internal/updates/schedule` — authenticated worker schedule-report endpoint
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

1. Worker briefly reads the enabled competition and request plan, then releases that database connection
2. Worker fetches provider schedule/state and eligible pregame odds without an open database session
3. Worker maps provider team IDs to the API-seeded catalog, stores non-FBS opponents from FBS schedules without granting FBS membership, and commits games, odds, alert events, and queued deliveries in one write transaction
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
3. Worker writes a deduplicated `alerts` event with an event-time score/status snapshot and channel-specific Email and/or Push `alert_deliveries` rows
4. The transaction commits before the scheduler wakes the process-local delivery thread
5. The delivery thread claims one pending row in a short transaction, sends with no database connection held, and saves the outcome in another short transaction
6. Web reads alert history through `/alerts/history`

The delivery thread drains once at worker startup and otherwise sleeps until a committed sync signals it; it does not poll the database. Provider failures are terminal. A row claimed before a worker interruption remains `pending` with `attempted_at` set and is marked failed on restart rather than resent, favoring at-most-once delivery over possible duplicate or stale sports alerts. Admin test alerts remain synchronous but also release their database transaction before calling Email or Push providers.

### Admin / Ops

Admin-only routes expose:

- alert and delivery activity
- DB health views
- Neon usage when configured
- competition enable/disable controls
- test tools

Admin opens on Leagues and loads its summary. Neon usage loads on demand when Activity & tools is first opened and otherwise reuses cached data. Neither dataset has periodic, focus, or reconnect refetching. Refresh reloads both datasets on Activity & tools and only the summary on Leagues. Changing the activity window fetches that summary; switching internal tabs reuses cached data. Competition-setting changes still refresh the summary, and failed reads retain cached values with an error. Already-requested reads retain the normal bounded retry and can resume after an offline pause.

The Admin Leagues tab combines availability controls and sync schedules from the worker's actual in-memory schedule. The worker posts a complete snapshot to `/internal/updates/schedule` after startup competition discovery, changes to its scheduled leagues, each queued catalog cycle, and each successful or failed job. The API authenticates with the existing live-update secret and atomically replaces one memory-only report. The admin summary includes this snapshot without additional SQL. Reports never invalidate the game feed or broadcast SSE events. They use the same timeout, single transient retry, and failure/recovery log suppression as [game notifications](#game-sync); delivery failures do not change job outcomes or scheduling. There are no reporting-only wake-ups. Local countdowns run only while Leagues is selected and the page is visible and make no requests; passed times require a manual refresh rather than implying a completed sync.

Admin has two mounted panels, ordered Leagues then Activity & tools. Hidden panels retain selections, disclosures, and results. Leagues shows enabled/disabled indicators, inline availability controls, next live syncs, and live intervals. Its header contains one shared catalog countdown from `next_catalog_at`, with catalog exceptions in a disclosure. Activity & tools combines alert activity, database usage, and the test-alert form; these appear side by side on desktop and stack on smaller screens. Test inputs are disabled while sending, duplicate submissions are blocked, and the response is displayed directly without a summary reload.

Admin test alerts use transient sample objects to exercise the real Email and Push delivery paths. They return channel outcomes in Activity & tools without entering game, alert history, or activity tables.

## Database Activity Observability

Both runtime processes aggregate existing SQLAlchemy connection, statement, transaction, and error events in memory. Every five minutes, nonempty `Database usage` summaries identify API route templates, worker scans/jobs, cache use, UTC activity minutes, and the deployed revision. A pure ASGI context middleware attributes API calls without buffering SSE. The logger never queries Postgres or retains a DB session. See the [runbook](runbook.md#reviewing-database-awake-time-and-waste) for the Neon snapshot and Render summary commands; observed activity is not a substitute for Neon’s actual awake-time counters.

## Design Constraints

- The worker is separate so ingest and delivery do not block request/response traffic
- Alert delivery is a process-local outbox dispatcher for the single worker, not a distributed queue; scaling to multiple workers would require revisiting its wake-up and claiming model
- Scheduler state and the API schedule report are process-local. Admin shows last reported plans, not worker liveness; worker logs remain the source of truth for actual execution and failures. API restarts clear its report until the next worker publication (potentially 12 hours later), and worker restarts clear remembered success times.
- SSE fanout and the dashboard feed cache are process-local and assume one API process on one instance; multiple processes or instances require shared broadcasting and cache invalidation
- Odds are persisted and read from the DB instead of fetched from the browser path
- RBAC is DB-backed through `users.role`
- Settings are strict enough that missing required env values fail early
- Sports-domain data is operationally disposable compared with user identity/auth data
