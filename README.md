# Sports Alerts Platform

Sports Alerts is a personal project for following live games and sending rule-based email and Web Push alerts. The repo is organized as a small multi-service system: a React web app, a FastAPI API, a background worker, and a Postgres database.

The current product surface supports five leagues: `NBA`, `WNBA`, `MLB`, `MLS`, and `WORLD_CUP`.

The live production site is [livegamealerts.com](https://livegamealerts.com).

## What The App Does Today

- Email magic-link and one-time-code sign-in with JWT-backed API sessions.
- Public `Games` dashboard with league/day filters, live status, follow/unfollow actions, and game-level alert settings.
- Public `Teams` directory with league/search filters and team follow controls.
- Authenticated Games filter for direct and team-derived follows.
- `Alerts` dashboard for league defaults plus alert history.
- Admin-only runtime area for provider telemetry, DB stats, league enable/disable controls, and test tools.
- Background ingest and alert evaluation worker with persisted game state and alert delivery history.
- Optional moneyline odds display when odds snapshots are available.
- Code-owned league profiles pair league-specific provider configuration with shared basketball, baseball, or soccer behavior.

Alert types are defined by sport and exposed independently for each league:

- `NBA` and `WNBA`: `game_start`, `close_game_late`, `final_result`
- `MLB`: `game_start`, `inning_start`, `final_result`
- `MLS` and `WORLD_CUP`: `game_start`, `second_half_start`, `extra_time_start`, `penalty_kicks`, `score_changed`, `final_result`

## Repo Layout

- `apps/web` — React + Vite frontend
- `services/api` — FastAPI API, auth, reads/writes, admin endpoints, Alembic migrations
- `services/worker` — schedule ingest, odds snapshots, alert evaluation, and delivery
- `infra/docker-compose.yml` — local multi-service stack
- `docs` — focused support docs for architecture, local development, configuration, deployment, and troubleshooting

## Quick Start

1. Run `make setup`
2. Fill in required values in `.env`
3. Run `make rebuild`
4. Open:
   - Web: `http://localhost:5173`
   - API docs: `http://localhost:8000/docs`
   - API health: `http://localhost:8000/healthz`

For the exact env shape, see [docs/configuration.md](/Users/rdettling/Library/Mobile Documents/com~apple~CloudDocs/Code/projects/sports-alerts-platform/docs/configuration.md).

## Day-To-Day Commands

- `make setup` — create `.env` if missing and install local dependencies
- `make up` — start the existing Docker stack
- `make rebuild` — rebuild app images and restart the stack
- `make down` — stop the stack and keep DB data
- `make reset` — stop the stack and remove DB volumes
- `make logs` — tail logs for all services
- `make logs SERVICE=api` — tail a single service
- `make test` — run API and worker tests plus web formatting, lint, tests, and build

## Architecture At A Glance

- The web app talks only to the API.
- The API owns auth, user-facing reads/writes, admin endpoints, and startup seeding.
- The worker owns schedule sync, odds snapshots, alert evaluation, and delivery execution.
- Postgres stores users, teams, games, follows, alert settings, sent alerts, odds snapshots, and lightweight ops data.
- League runtime is DB-backed through `league_settings`, so a league can be disabled without redeploying.

## Canonical Docs

- [docs/architecture.md](/Users/rdettling/Library/Mobile Documents/com~apple~CloudDocs/Code/projects/sports-alerts-platform/docs/architecture.md) — services, flows, and persisted state
- [docs/local-development.md](/Users/rdettling/Library/Mobile Documents/com~apple~CloudDocs/Code/projects/sports-alerts-platform/docs/local-development.md) — setup, daily workflow, and local verification
- [docs/configuration.md](/Users/rdettling/Library/Mobile Documents/com~apple~CloudDocs/Code/projects/sports-alerts-platform/docs/configuration.md) — env vars and config groups
- [docs/deployment.md](/Users/rdettling/Library/Mobile Documents/com~apple~CloudDocs/Code/projects/sports-alerts-platform/docs/deployment.md) — deployment shape and post-deploy checks
- [docs/runbook.md](/Users/rdettling/Library/Mobile Documents/com~apple~CloudDocs/Code/projects/sports-alerts-platform/docs/runbook.md) — troubleshooting and recovery

## Deployment Note

The project has a production-style deployment shape and can be hosted on services like Render plus a managed Postgres provider such as Neon. See [docs/deployment.md](/Users/rdettling/Library/Mobile Documents/com~apple~CloudDocs/Code/projects/sports-alerts-platform/docs/deployment.md) for the reference model.
