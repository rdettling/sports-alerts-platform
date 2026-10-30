# Runbook

## API Unreachable From The Frontend

Symptoms:

- sign-in fails because the browser cannot reach the API
- dashboard data requests fail immediately

Checks:

1. Confirm `VITE_API_BASE_URL` points at the correct API origin
2. Confirm `GET /healthz` is healthy
3. Confirm `CORS_ALLOW_ORIGINS` includes the frontend origin
4. Check `make logs SERVICE=api` for startup or config failures


## Admin Data Is Stale Or Requesting Unexpectedly

Admin loads on demand; see the [request and panel rules](architecture.md#admin--ops). Reload Admin when current data is required after leaving it open or returning from another app. After a partial failure, cached content remains visible beside errors.

To verify request behavior in browser network tools:

1. Open Admin, then open Activity & tools once so the summary-backed panels are visible.
2. Leave it visible for ten minutes, switch tabs, return from another app, and restore networking. These actions must not start additional `/ops/admin/summary` requests; an already-requested offline load can resume.
3. Confirm there is no manual refresh control on either tab.
4. Change the activity window or a league setting: expect a summary request. Sending a test alert displays its delivery response without requesting another summary.

If requests exceed those expectations, check the frontend revision and distinguish deliberate actions and bounded retries from polling. For stale schedules, follow the checks below.

## Admin League Sync Times

For the [reported schedule](architecture.md#admin--ops), compare scheduled league deadlines with worker logs. `No upcoming games` means the live job is dormant until catalog discovers eligible work; it does not have a hidden live-sync deadline. A passed time is not proof of completion: reload Admin, then inspect logs if the report remains old. Reloading reads API memory and does not contact the worker.

Backend startup immediately starts the scheduler and publishes its first plan. An enabled league absent from the report is awaiting discovery; a disabled league still present is awaiting confirmation. Check worker startup time before interpreting missing last-success values, which reset on worker restart.

If reports stay unavailable, check `/healthz` and backend startup logs. Schedule reports are shared in process; there is no internal HTTP endpoint or shared secret to configure.

`Catalog cycle queued` logs show the league count and UTC slot. Job result logs report the actual `next_run_at` (unset when dormant) separately from `next_catalog_at`; an odds deadline is the next eligible sweep, not the next catalog cycle. Verify that completion times do not move the regular UTC schedule, retries affect only the failing league, and the next regular cycle replaces pending retries. Consult [worker scheduling](architecture.md#worker-scheduling) for startup and missed-cycle behavior.

## Games Screen Is Stale

1. Check worker `Job completed` logs for changed games. Upstream fetch cadence is separate from display latency: basketball, football, and NHL use one minute, soccer 90 seconds, and MLB two minutes
2. Confirm the backend started one scheduler and one delivery thread; `/healthz` reports a stopped thread
3. On a visible, online Games screen, inspect `/updates/games`: expect `text/event-stream`, periodic keep-alives, and `games` events after changed syncs
4. An event should prompt a games read after about one second (at least two seconds between event-driven reads). The API invalidates its shared cache before sending the event
5. Without events, expect a fallback read after 60 seconds for a live feed, or after 30 minutes for a quiet feed. An earlier future scheduled start brings the quiet check forward. Initial load failures use 60 seconds; subsequent failures use the last known feed. Cache entries expire after 30 seconds even if a worker notification was lost
6. Game changes invalidate the local cache and schedule an SSE broadcast on the API event loop; no worker-to-API network request is involved
7. Verify the API still uses one process on one instance. Process-local notifications and invalidation do not span replicas

Hidden/offline screens intentionally stop SSE and refresh timers. On an iPhone, reopen the Home Screen app and verify a catch-up request and a new stream connection. Render deployments also interrupt existing streams; reconnection must fetch the latest state. Existing displayed games remain visible during background refreshes. Failed reads use the existing error display and retry/fallback behavior.

The five-second normal update target assumes healthy services/networking and a visible app. Two-minute missed-notification recovery applies when the feed already shows live games; quiet feeds use a fallback of up to 30 minutes. A delayed or overdue scheduled game does not by itself trigger minute-by-minute reads. Display refreshes cannot accelerate upstream sports data or keep iOS running in the background.

## Frontend Route 404 On Hard Refresh

Symptoms:

- direct browser refresh on a nested route returns `404`

Fix:

- configure SPA fallback / rewrites on the frontend host

## Email Sign-In Issues

Checks:

1. Confirm the API is reachable and healthy
2. Confirm `WEB_BASE_URL` points at the frontend origin users should land on
3. Confirm delivery mode is intentional:
   - `DELIVERY_MODE=log` for local inspection
   - `DELIVERY_MODE=live` for real delivery
4. For live email, confirm `RESEND_API_KEY` and `FROM_EMAIL` are valid
5. Check API logs for sign-in email rate limiting or delivery warnings
6. For an installed iPhone or iPad Home Screen app, enter the emailed code in the app; opening the link authenticates Safari instead

## Odds Not Showing

Checks:

1. Confirm `ODDS_API_KEY` is nonblank and valid if you expect odds
2. Confirm the worker is running
3. Admin reports each odds job's `last_outcome` separately from its next deadline. Request failures and missing configuration remain visible until the next attempt; they do not advance `last_success_at`.
4. Filter worker logs by `competition=FBS` (or the affected league). `Odds sweep finished` records `outcome`: `fetched`, `fetch_failed`, `quota_failed`, `budget_limited`, `missing_api_key`, or `no_eligible_games`.
5. For failed requests, `Odds request failed` identifies `stage=quota` or `stage=prices`, duration, configured timeout, exception type, nested reason type, and HTTP status. Request URLs, API keys, and raw exception messages are omitted.
6. For successful requests, `Odds coverage` shows parsed provider moneyline matchups, checked games, saved odds, and unmatched games. Its sample contains at most five unmatched game IDs, teams, and start times. Zero parsed matchups means no usable moneylines; nonzero matchups with missing games calls for comparing provider coverage, team names, and kickoff times.

Expected behavior:

- when `ODDS_API_KEY` is blank, games still load but odds values can be empty
- odds sweeps run after each league's startup catalog attempt (including deploys and restarts), then at 00:00 and 12:00 UTC for unpriced eligible games within 48 hours; fetch and quota failures wait for the next sweep, without immediate retries
- startup sweeps retain the persisted daily credit cap and provider reserve, and do not move the regular UTC schedule
- Saved odds invalidate the game feed cache and publish a game update just like score changes. No odds change means no update event.
- `outcome=fetched` means the request succeeded, even when no odds matched; request failures have explicit failure outcomes

## Worker Running But Alerts Not Arriving

Checks:

1. Confirm the worker is running and logging sync activity
2. Confirm a relevant competition is active in Admin (`competition_settings.is_enabled = true`)
3. Confirm users follow teams or games that should produce alert candidates
4. Confirm the resolved competition or per-game settings have the alert type enabled; per-game fields inherit competition values until explicitly changed
5. For real delivery, confirm `DELIVERY_MODE=live`
6. For email failures, confirm the Resend settings
7. For Push failures, confirm `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT`, then inspect the aggregate `provider_data`
8. Inspect `alerts`, `alert_deliveries`, and worker logs for dedupe or delivery failures

## Push Not Available Or Not Arriving

Checks:

1. Confirm the Alerts page reports Push as configured
2. Confirm notification permission is granted for the site
3. On iPhone or iPad, confirm the site was added to the Home Screen and opened from there
4. Confirm the current device is subscribed on the Alerts page
5. Confirm Push is enabled on the intended device; email settings do not control Push enrollment
6. Check the push delivery row; expired endpoints (`404` or `410`) are removed automatically

Push has no email fallback. Email alerts and per-device Push enrollment are independent.

## Competition Availability

Admin is the source of truth for which supported competitions are active. Inactive competitions remain listed in Admin but disappear from Games, Teams, follows, alert configuration, and each user's league picker. Their stored sports data and user choices are preserved for reactivation.

New competition profiles added to an existing environment start inactive. Review their provider configuration and team catalog, then activate them from Admin when they are ready to consume sync resources and appear throughout the app. Seasonal activation is manual; the app does not infer availability from calendar dates or temporary gaps in scheduled games.

For the NHL rollout, deploy the migration and API first so startup seeding creates the 32-team catalog and inactive `NHL` row. Confirm the Admin league entry and team catalog, deploy the web app, then enable NHL manually. Preseason games should ingest normally with `is_odds_eligible = false`.

## Bad Local State

Escalation path:

1. `make down`
2. `make up`
3. `make rebuild`
4. `make reset`

`make reset` deletes local DB data, including local sign-in/session state in the database.

## Strict Env Startup Failures

Symptoms:

- API or worker exits during startup with settings validation errors

Fix:

- make sure required values exist in `.env` or your deployed service environment
- use [configuration.md](configuration.md) as the source of truth

## SQLite Storage and Recovery

Confirm `DATABASE_URL` points into the persistent disk, check free disk space, and verify only one backend process is running. WAL permits concurrent readers but serializes writers; an unusually long write transaction can exhaust the 30-second lock wait. Provider requests should not hold write transactions open.

Daily snapshots are under the database directory's `backups` folder. Follow [backup and recovery](deployment.md#backups-and-recovery) to create an additional consistent snapshot, copy it off the service, or restore while stopped. Do not remove WAL sidecars while the backend is running.
