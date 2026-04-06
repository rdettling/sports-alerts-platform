# Sports Alerts Platform — V1 Implementation Plan

## Goal

Build a backend-heavy sports alerts platform optimized for resume value and realistic completion. The product should let a user follow NBA teams or specific games and receive email notifications for key game events.

The system should be designed so V1 can launch for a single user, but the architecture should be multi-user ready from the start.

---

## Finalized V1 Decisions

- **League scope:** NBA only
- **Delivery method:** Email only
- **Alert types:**  
  - game start
  - close game late
  - final result
- **Architecture:** separate API service + background worker / scheduler
- **User model:** launch as effectively single-user, but build data model and backend as multi-user capable

---

## Product Definition

### User-facing behavior

A user can:

- create an account or otherwise exist as a user entity in the system
- follow one or more NBA teams
- optionally follow specific games
- configure which of the 3 alert types they want
- receive email alerts
- view current subscriptions and alert history in the web app

### Alert types in V1

1. **Game start**
   - send when a followed game starts, or when the game status changes to live

2. **Close game late**
   - send when the score margin is within a configurable threshold late in the game
   - default V1 rule: margin <= 5 points in the final 2 minutes of regulation or overtime
   - only send once per game per user for this alert type

3. **Final result**
   - send when the game ends

---

## Core Engineering Goal

This project should be built as a real backend system, not just a dashboard.

The strongest resume signals should come from:

- external data ingestion
- scheduled/background processing
- rule evaluation
- notification delivery
- deduplication/state tracking
- multi-user-ready backend design

The UI should stay simple.

---

## Suggested Tech Stack

Use a stack that is straightforward to implement and cheap to host.

### Frontend
- React
- Vite
- minimal responsive UI

### Backend API
- Python
- FastAPI

### Database
- Postgres

### Background processing
- one worker process
- scheduler / polling loop
- keep implementation simple; avoid unnecessary infrastructure unless clearly needed

### Email
- a low-cost transactional email provider

### Deployment target
Keep total monthly cost under roughly $20.

A good target deployment shape:

- frontend: static hosting
- API service: one small web service
- worker/scheduler: one small background service or cron-driven worker
- Postgres: lowest-cost viable option

---

## Architecture Overview

Build the system as 3 logical components.

### 1. Frontend
Responsibilities:

- user login / account access
- manage followed teams
- manage followed games
- manage alert preferences
- display alert history
- optionally show simple upcoming/live games list

### 2. API service
Responsibilities:

- auth / user management
- CRUD for subscriptions
- CRUD for alert preferences
- expose game/team data to frontend
- expose alert history
- enqueue or record work for worker when needed

### 3. Worker / scheduler
Responsibilities:

- poll external NBA data source on a schedule
- normalize incoming game data
- update game state in DB
- evaluate alert rules for affected games/users
- create notification records
- send emails
- record delivery results
- dedupe alerts so users are not spammed

---

## Multi-User-Ready Approach

Even if V1 is initially used by only one person, the backend should be built as if many users could be added later.

That means:

- every subscription belongs to a user
- every alert preference belongs to a user
- every sent notification belongs to a user
- deduplication should be per user, per game, per alert type

Do **not** hardcode single-user assumptions into the data model.

---

## Recommended Data Model

Use roughly these tables.

### users
Fields:
- id
- email
- password_hash or auth provider fields
- created_at
- updated_at

### teams
Fields:
- id
- external_team_id
- league
- name
- abbreviation

### games
Fields:
- id
- external_game_id
- league
- home_team_id
- away_team_id
- scheduled_start_time
- status
- home_score
- away_score
- period
- clock
- is_final
- last_ingested_at
- created_at
- updated_at

### user_team_follows
Fields:
- id
- user_id
- team_id
- created_at

### user_game_follows
Fields:
- id
- user_id
- game_id
- created_at

### user_alert_preferences
Fields:
- id
- user_id
- alert_type
- is_enabled
- close_game_margin_threshold
- close_game_time_threshold_seconds
- created_at
- updated_at

For V1, it is acceptable to store one preference row per user per alert type.

### sent_alerts
Fields:
- id
- user_id
- game_id
- alert_type
- delivery_channel
- delivery_status
- sent_at
- provider_message_id
- dedupe_key
- metadata_json

### ingest_runs
Fields:
- id
- started_at
- completed_at
- status
- games_checked
- games_updated
- error_message

This is optional but useful for debugging and observability.

---

## External Data Ingestion Strategy

Use polling for V1.

### Initial polling approach
- periodically fetch NBA schedule and game status data from a free/public source
- normalize responses into internal game model
- update only changed fields when possible

### Polling frequency guidance
Use simple, pragmatic rules:

- **Games not starting soon:** poll infrequently
- **Games starting soon:** poll more often
- **Games currently live:** poll most frequently
- **Final games:** stop polling aggressively

Example approach:
- live games: every 30–60 seconds
- games starting soon: every 2–5 minutes
- other games on the same day: every 10–15 minutes

Do not over-engineer this at first. Keep it simple and cheap.

---

## Alert Rule Logic

### Game start
Trigger when:
- game status transitions into live / in-progress

Deduplication:
- only one game-start alert per user per game

### Close game late
Default V1 rule:
- score difference <= 5
- final 2 minutes of regulation or overtime

Notes:
- if source data is imperfect, implement best-effort logic using available game clock / period fields
- only send once per user per game for this alert type

### Final result
Trigger when:
- game status transitions to final

Deduplication:
- only one final-result alert per user per game

---

## Deduplication Design

This is important.

The worker must prevent repeated sends when the same condition is observed multiple polling cycles.

Implement a dedupe strategy such as:

- dedupe key = user_id + game_id + alert_type

Before sending an alert:
- check whether a sent_alert already exists for that dedupe key
- if yes, skip send
- if no, send and persist the sent_alert row

For future extensibility, keep dedupe logic centralized.

---

## API Scope for V1

Keep the API small and clean.

### Auth / user
- create account
- log in
- get current user

### Teams / games
- list supported teams
- list upcoming/live games
- get game details

### User follows
- follow team
- unfollow team
- follow game
- unfollow game
- list current follows

### Alert preferences
- get user alert preferences
- update alert preferences

### Alerts
- list alert history

You do not need a large API surface.

---

## Frontend Scope for V1

The frontend should be intentionally light.

### Required pages/views
- login / auth
- dashboard
- followed teams
- followed games
- alert preferences
- alert history

### Nice-to-have if easy
- simple upcoming/live games list
- quick “follow this game” action

### Explicit non-goals
- polished ESPN-like browsing
- detailed stats views
- rich charts
- advanced search UX
- native mobile app

Keep the UI functional and clean.

---

## Worker / Scheduler Scope

The worker is the heart of the system.

### Main loop responsibilities
1. determine which games need polling
2. fetch fresh data
3. update DB state
4. determine which users are affected
5. evaluate rules
6. send alerts
7. persist sent alerts and statuses
8. record ingest run metadata / errors

### Error handling
- failed provider calls should not crash the whole loop
- failed email sends should be logged and marked failed
- retries can be basic in V1

### Logging
Add structured logs for:
- ingest start/end
- games updated
- alert evaluations
- alerts sent
- email failures

---

## Authentication Guidance

Because V1 starts with one user but should remain multi-user ready, use a simple auth approach.

Recommended options:
- email/password
- magic link

Prefer the easiest option that does not complicate hosting.

Do not skip user modeling entirely.

---

## Cost Constraint Guidance

Design choices should prioritize staying under about $20/month.

### Cost-saving principles
- one league only
- polling only
- email only
- minimal frontend
- small Postgres instance
- no paid Redis unless clearly necessary
- no native mobile app
- no overbuilt microservices

### What to avoid in V1
- separate queue infrastructure unless truly needed
- expensive third-party sports APIs
- push notification infrastructure
- analytics platforms you do not need
- premium observability tooling

---

## Deployment Guidance

A simple deployment shape is enough.

### Recommended deployment shape
- frontend: static host
- API: one small web service
- worker: one background worker or cron-driven process
- DB: Postgres

### Important deployment requirement
The API and worker should be separate logical runtime components, even if hosted in the same overall platform.

This gives better project signal and cleaner architecture.

---

## Resume Value Targets

This project should eventually support a resume bullet like:

- Built a sports alerting platform that ingested live NBA data, evaluated user-defined notification rules, and delivered personalized email alerts through scheduled jobs and asynchronous workers with deduplication and delivery tracking.

Alternative phrasing:

- Built a multi-user-ready sports event notification platform with a FastAPI backend, background polling workers, rule-based alerting, and email delivery for live NBA game events.

The implementation should aim toward making one of those statements fully true.

---

## V1 Milestones

### Milestone 1 — skeleton
- initialize repo
- set up frontend, backend, DB
- define schema
- wire local development setup
- add basic auth
- add teams/games models

### Milestone 2 — subscriptions
- follow teams
- follow games
- store alert preferences
- build simple dashboard UI

### Milestone 3 — ingestion
- implement NBA polling
- normalize game data
- persist game updates
- add simple logging

### Milestone 4 — alert engine
- implement game start, close game late, final result rules
- implement dedupe logic
- persist sent alerts

### Milestone 5 — email delivery
- send email alerts
- record delivery results
- display alert history in UI

### Milestone 6 — polish
- improve error handling
- improve polling efficiency
- refine UI
- add README and architecture notes
- prepare for deployment

---

## Explicit Non-Goals for V1

Do not include these in V1:

- multiple leagues
- news alerts
- betting/odds features
- native mobile app
- push notifications
- live websockets
- social features
- advanced analytics dashboards
- AI summaries
- fantasy integrations

These can be future versions if desired.

---

## V2 / V3 Ideas (Optional Future Roadmap)

### V2
- add NFL
- add web push notifications
- add quiet hours / notification windows
- add better live game browsing
- improve worker scheduling efficiency

### V3
- user-defined thresholds for close-game alerts
- richer notification rules
- websocket/live updates
- PWA/mobile improvements
- digest mode
- admin/ops dashboard

---

## Implementation Philosophy

Prioritize:

1. backend correctness
2. clear data model
3. rule evaluation logic
4. deduplication
5. clean deployment shape
6. simple UI

Do **not** sacrifice backend/system depth for frontend polish.

The project should feel like a real backend platform with a lightweight web UI attached.
