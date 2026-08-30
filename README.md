# Sports Alerts Platform

Sports Alerts is a personal project for following live games and sending rule-based email and Web Push alerts. The repo is organized as a small multi-service system: a React web app, a FastAPI API, a background worker, and a Postgres database.

The current product surface supports nine competitions: `NBA`, `WNBA`, `NFL`, `FBS`, `MLB`, `MLS`, `LA_LIGA`, `PREMIER_LEAGUE`, and `WORLD_CUP`.

The live production site is [livegamealerts.com](https://livegamealerts.com).

## What The App Does Today

- Email magic-link and one-time-code sign-in with JWT-backed API sessions.
- Public `Games` dashboard with competition/day filters, live status, follow/unfollow actions, and game-level alert settings.
- Public canonical `Teams` directory with competition/search filters, membership badges, and one follow state per team across every competition.
- FBS conference filtering on Games plus collapsible conference groups and followed-team prioritization in Teams.
- Authenticated Games filter for direct and team-derived follows.
- `Alerts` dashboard for sport-wide defaults plus alert history.
- Admin-only operations area for alert delivery activity, DB stats, competition controls, and test tools.
- Background ingest and alert evaluation worker with persisted game state and alert delivery history.
- Optional moneyline odds display when odds snapshots are available.
- Code-owned competition profiles pair competition-specific provider configuration with shared basketball, football, baseball, or soccer behavior.

Alert types default by sport and can be restricted for a specific competition:

- `NBA`, `WNBA`, `NFL`, and `FBS`: `game_start`, `close_game_late`, `overtime_start`, `final_result`
- `MLB`: `game_start`, `inning_start`, `extra_innings_start`, `final_result`
- `MLS` and `WORLD_CUP`: `game_start`, `second_half_start`, `extra_time_start`, `penalty_kicks`, `score_changed`, `final_result`
- `LA_LIGA` and `PREMIER_LEAGUE`: `game_start`, `second_half_start`, `score_changed`, `final_result`

## Repo Layout

- `apps/web` — React + Vite frontend
- `services/backend/app` — FastAPI API, auth, reads/writes, admin endpoints, and delivery helpers
- `services/backend/app/worker` — schedule ingest, odds snapshots, alert evaluation, and delivery
- `services/backend/alembic` — database migrations shared by both backend processes
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

For the exact env shape, see [docs/configuration.md](docs/configuration.md).

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
- Competition availability is DB-backed through `competition_settings`: supported leagues remain manageable in Admin, active leagues consume worker resources and appear throughout the app, and signed-in users can hide active leagues for themselves.

## Canonical Docs

- [docs/architecture.md](docs/architecture.md) — services, flows, and persisted state
- [docs/local-development.md](docs/local-development.md) — setup, daily workflow, and local verification
- [docs/configuration.md](docs/configuration.md) — env vars and config groups
- [docs/deployment.md](docs/deployment.md) — deployment shape and post-deploy checks
- [docs/runbook.md](docs/runbook.md) — troubleshooting and recovery

## Deployment Note

The project has a production-style deployment shape and can be hosted on services like Render plus a managed Postgres provider such as Neon. See [docs/deployment.md](docs/deployment.md) for the reference model.
