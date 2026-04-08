# Functionality (Current State)

This document describes what the app currently does in production code.

## Authentication

- Register with email/password.
- Login with email/password.
- JWT bearer auth for protected API routes.
- Session persistence in frontend local storage.

## Games Tab

- Lists non-final games from API (`/games`) sorted by scheduled time.
- Filters:
  - `All`
  - `Live` (status `in_progress` or `live`)
  - `Today`
  - `Following` (games the user follows)
- Each row shows:
  - game time (or live clock/period when in progress)
  - matchup + team logos
  - no-vig win probability split (when odds exist)
  - moneyline odds + bookmaker (when odds exist)
  - follow/unfollow action
- Auto-refresh every 2 minutes + manual refresh button.

## Following Tab

- Two panels: `Teams` and `Games`.
- Teams panel:
  - follow team from dropdown
  - unfollow followed teams
- Games panel:
  - `Active` followed games
  - `Recent 24h` completed followed games
  - completed games show final score snippet
  - unfollow per game
- Manual refresh button.

## Alerts Tab

- Health cards:
  - last sent timestamp
  - sent count (24h)
  - failed count (24h)
- Alert Rules:
  - `game_start`
  - `close_game_late` (margin + minutes controls)
  - `final_result`
- Rule toggles persist immediately.
- Alert history list supports filters:
  - alert type
  - time window (`24h`, `7d`, `all`)
  - delivery status (`all`, `sent`, `failed`, `pending`)
- Auto-refresh every 2 minutes.

## Dev Test Tab (Optional)

- Visible only when `DEV_MODE=true` in frontend env.
- Lets you enqueue test alerts through `/alerts/dev/test-email`.
- Intended for local/dev validation of delivery flow.

## Worker Behavior

- Polls NBA provider schedule and updates.
- Upserts teams/games state into Postgres.
- Evaluates alert rules for followers.
- Writes pending alerts to `sent_alerts` with dedupe keys.
- Delivers pending alerts via configured delivery mode:
  - `log`
  - `email` (Resend)

## Odds Behavior

- Odds ingestion can be controlled via:
  - `ODDS_ENABLED`
  - `ODDS_REFRESH_SECONDS`
- Worker only fetches odds when relevant games exist and refresh window has elapsed.
- Odds mapping protects against repeated-matchup collisions by matching event start times.
- If only far-away matchup odds exist, stale odds are not reused.
