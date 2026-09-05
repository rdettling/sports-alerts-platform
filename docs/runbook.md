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

## Reviewing Database Awake Time And Waste

Neon usage snapshots measure actual project compute consumption; Render application logs explain which app activity contributed to keeping the database busy. Render's own API/worker CPU charts describe those containers, not the Neon database.

At deployment and again after at least a day, run from the repo root:

```sh
python3 scripts/neon_usage_snapshot.py --project-id solitary-resonance-98873129
python3 scripts/database_usage_report.py --resources srv-d79kbthr0fns73eietr0,srv-d79kfgqdbo4c73adcthg --hours 24
```

Snapshots are saved under `.cache/neon-usage/`; compare only the same project and billing period. Missing usage counters are unavailable, never zero. Neon counters may lag, so avoid conclusions from short intervals. A snapshot captured before deployment is only a baseline for the old deployment; capture another at cutover for a clean comparison.

The API and worker emit `Database usage {…}` JSON summaries every five minutes when activity exists, plus a partial summary on graceful shutdown. Each includes the deployed revision and bounded source groups:

- `api:GET /games` and other API route templates: connections, statement executions, commits, rollbacks, and errors
- `worker:competition_scan`: scheduler reads outside ingest jobs
- `worker:live_sync:FBS`, `worker:catalog_sync:MLB`, etc.: database work attributed to each job; correlate with existing `Job completed` logs for games checked/changed and next-run timing
- `api:startup`: startup seed work
- Game cache hits, fills, and discarded fills: cache hits should require no connection; repeated fills without changed worker data can expose excessive refreshes

`db_minutes` identifies UTC minutes containing observed database activity, including failed calls. The report unions these across services, ranks sources by connection count, and shows activity by UTC hour to help locate quiet-period polling. These minutes are **not** actual awake hours: Neon can remain awake after the last query, and external clients can cause activity absent from these logs. SQL statement counts represent execution calls, not rows, database CPU time, or all internal driver traffic. Read-only session cleanup also produces rollbacks; a rollback count alone does not mean failed work.

To judge waste, compare awake hours and CU-hours from snapshots, identify activity during periods without live games, then check whether it came from game-feed fills, admin polling, startup, or worker scans. Look for repeated unchanged worker syncs and many discarded cache fills. Keep the old and new deployment revisions separate. Fast reconnects or many staggered viewers may still keep Neon awake even with the quiet fallback.

Check the [worker schedule rules](architecture.md#worker-scheduling) and the next reported job time before treating a quiet interval or delayed league discovery as a failure. Catalog clustering may reduce scattered activity, but compute-hour savings must be measured.

To verify idle sleep after a worker deploy, capture a fresh usage snapshot and confirm the startup log reports `idle_max_sleep=43200s` with the default catalog interval. Review an overnight period without live games: `worker:competition_scan` should not appear hourly between scheduled jobs. Correlate its timestamps with `start_compute` and `suspend_compute` from `neon operations list --project-id solitary-resonance-98873129 -o json`. This reads Neon's control plane without waking Postgres. Attribute site visits, admin polling, scheduled catalog jobs, and failure recovery separately; fewer application queries alone do not establish fewer awake hours.

Logging only counts existing operations in memory and flushes to stdout. It issues no SQL, stores no rows, keeps no database connection, and logs no SQL text, parameters, credentials, user IDs, or raw request URLs. SSE traffic passes through without buffering and causes no DB activity by itself.

If admin requests appear repeatedly during idle periods, use the [Admin refresh checks](#admin-data-is-stale-or-refreshing-unexpectedly). Deliberate refreshes still authenticate against Postgres, including the Neon usage endpoint whose usage lookup itself uses the control plane.

The report requests up to 1,000 summary records and warns if that limit is reached; use smaller windows in that case. Current partial windows and abruptly terminated processes can be missing. Empty windows are not emitted, so no logs alone cannot prove the process was healthy or Neon was asleep. [Render retains Hobby logs for seven days](https://render.com/docs/logging), enough for a next-day review. Capture the report before retention expires.

## Admin Data Is Stale Or Refreshing Unexpectedly

Admin loads on demand; see the [refresh and panel rules](architecture.md#admin--ops). Use Refresh after leaving it open or returning from another app. After a partial failure, cached content remains visible beside errors.

To verify request behavior in browser network tools:

1. Open Admin, then open Activity & tools once so both the summary and Neon usage have loaded.
2. Leave it visible for ten minutes, switch tabs, return from another app, and restore networking. These actions must not start additional `/ops/admin/summary` or `/ops/db/neon-usage` requests; an already-requested offline load can resume.
3. Click Refresh on Activity & tools: expect summary and Neon usage requests. On Leagues, expect only the summary.
4. Change the activity window or a league setting: expect a summary request. Sending a test alert displays its delivery response without requesting another summary.

If requests exceed those expectations, check the frontend revision and distinguish deliberate actions and bounded retries from polling. For stale schedules, follow the checks below.

## Admin League Sync Times

For the [reported schedule](architecture.md#admin--ops), compare Next catalog refresh and each league’s live deadline with worker logs. A passed time or Catalog pending is not proof of completion: use Refresh, then inspect logs if the report remains old. Refresh reads API memory and does not contact the worker.

Schedule unavailable can persist for up to 12 hours after an API restart while the worker sleeps. An enabled league absent from the report is awaiting discovery; a disabled league still present is awaiting confirmation. Check worker startup time before interpreting missing last-success values, which reset on worker restart.

If reports stay unavailable after worker activity, check `Schedule report delivery failed` and the matching recovery log, then verify the worker API URL/shared secret. During a release, confirm the API and worker use compatible schedule fields; see the [catalog cutover instructions](deployment.md#shared-catalog-schedule-cutover).

`Catalog cycle queued` logs show the league count and next shared deadline. Verify that completion times do not move that deadline, retries affect only the failing league, and the next regular cycle replaces pending retries. Consult [worker scheduling](architecture.md#worker-scheduling) for startup and missed-cycle behavior. Use `worker:catalog_sync:<league>` counters to attribute database activity separately from live polling and site visits.

## Games Screen Is Stale

1. Check worker `Job completed` logs for changed games. Upstream fetch cadence is separate from display latency: basketball/football use one minute, soccer 90 seconds, and MLB two minutes
2. Confirm `LIVE_UPDATE_API_URL` points to the API and both services have matching `LIVE_UPDATE_SECRET` values
3. On a visible, online Games screen, inspect `/updates/games`: expect `text/event-stream`, periodic keep-alives, and `games` events after changed syncs
4. An event should prompt a games read after about one second (at least two seconds between event-driven reads). The API invalidates its shared cache before sending the event
5. Without events, expect a fallback read after 60 seconds for a live feed, or after 30 minutes for a quiet feed. An earlier future scheduled start brings the quiet check forward. Initial load failures use 60 seconds; subsequent failures use the last known feed. Cache entries expire after 30 seconds even if a worker notification was lost
6. Look for `Live update delivery failed` and `Live update delivery recovered` in worker logs. Transient failures get one retry; repeated failures are log-suppressed
7. Verify the API still uses one process on one instance. Process-local notifications and invalidation do not span replicas

Hidden/offline screens intentionally stop SSE and refresh timers. On an iPhone, reopen the Home Screen app and verify a catch-up request and a new stream connection. Render deployments also interrupt existing streams; reconnection must fetch the latest state. Existing displayed games remain visible during background refreshes. Failed reads use the existing error display and retry/fallback behavior.

The five-second normal update target assumes healthy services/networking and a visible app. Two-minute missed-notification recovery applies when the feed already shows live games; quiet feeds trade recovery time (up to 30 minutes) for opportunities to suspend Neon. A delayed or overdue scheduled game does not by itself trigger minute-by-minute reads. Other viewers, worker jobs, and reconnects can still prevent suspension. Display refreshes cannot accelerate upstream sports data or keep iOS running in the background.

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
3. Check worker logs for odds fetch failures during catalog sync

Expected behavior:

- when `ODDS_API_KEY` is blank, games still load but odds values can be empty

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

## Bad Local State

Escalation path:

1. `make down`
2. `make up`
3. `make rebuild`
4. `make reset`

`make reset` deletes local DB data, including local sign-in/session state in the database.

## Complete Database Reset And Reseed

Use this only when you intend to delete users, login state, push subscriptions, follows, preferences, alerts, and sports data. The script rebuilds the database through the latest Alembic revision and restores the code-owned competition and team catalogs.

For a production baseline cutover, follow the ordered procedure in [deployment.md](deployment.md#clean-baseline-cutover). The reset must run from the new code before the new API starts.

1. Stop or pause the worker
2. Run:

```sh
cd services/backend
uv run python scripts/reset_database.py --yes
```

3. Restart API and worker
4. Confirm competitions and canonical teams were reseeded and ingest resumes cleanly
5. Sign in again and restore any desired follows and preferences

## Strict Env Startup Failures

Symptoms:

- API or worker exits during startup with settings validation errors

Fix:

- make sure required values exist in `.env` or your deployed service environment
- use [configuration.md](configuration.md) as the source of truth
