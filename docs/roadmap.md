# Roadmap

## Product Direction

Build a clean, reliable live-game alerts product where a user can quickly follow relevant games and receive timely, trustworthy alerts with minimal setup.

## Current Baseline

The app currently supports:

- Email/password auth with JWT sessions.
- Games listing with live/today/following filters.
- Team and game follows.
- Alert rule configuration (`game_start`, `close_game_late`, `final_result`).
- Alert history with filtering.
- Worker-based ingest and alert delivery pipeline.
- Optional moneyline odds display with no-vig probabilities.
- Email delivery through Resend (or log mode).

## Priorities

1. Improve alert quality and relevance.
2. Keep operational complexity and external API cost low.
3. Improve UX clarity and reduce friction for first-time users.
4. Prepare cleanly for multi-sport support after NBA model stabilizes.

## Next Milestones (Now)

### 1) Alert Quality Improvements

- Add richer rule options (for example: comeback momentum, upset alerts, tighter close-game tuning).
- Improve dedupe behavior to prevent noisy duplicate alerts.
- Add confidence/priority metadata to alert events for clearer ranking in UI.

### 2) Odds and Data Reliability

- Keep `ODDS_ENABLED` guardrails and low-frequency refresh controls.
- Improve odds freshness visibility in UI (last-updated indicator and stale-state messaging).
- Add provider-failure handling/telemetry for clearer operator debugging.

### 3) UX and Product Polish

- Continue dashboard clarity improvements (information density, hierarchy, states).
- Tighten empty/loading/error states across tabs.
- Improve email template presentation and consistency across alert types.

## Upcoming Milestones (Next)

### 4) Auth Simplification

- Evaluate reducing login friction while preserving account ownership and delivery security.
- Candidate direction: email-link / magic-link flow with clear device/session handling.
- Keep backward-compatible migration path only if needed; otherwise prefer clean replacement.

### 5) Following Intelligence

- Add optional “recommended follows” based on user-followed teams and current slate.
- Improve game ordering heuristics beyond pure start time.
- Lay groundwork for watchability scoring framework.

## Later Milestones

### 6) Multi-Sport Expansion

- Generalize provider and game normalization interfaces for additional leagues.
- Introduce per-league capability toggles (rules, ingest cadence, scoring semantics).
- Roll out one additional sport only after NBA parity criteria are met.

### 7) Additional Delivery Channels

- Keep email as primary channel.
- Evaluate push/SMS only after alert quality and economics are stable.

## Deployment Strategy

- Stay on Render + Neon in the near term.
- Prioritize reliability and cost controls within current stack.
- Re-evaluate infra migration only if scale or platform constraints become material.

## Definition of Done (per milestone)

A milestone is complete only when all are true:

- Behavior is implemented end-to-end (API, worker, and UI where applicable).
- Required env/config changes are documented in `docs/environment-variables.md`.
- Local run/test flow is still accurate in `README.md` and `docs/local-development.md`.
- Deployment implications are reflected in `docs/deployment-render.md`.
- User-facing behavior is observable via clear UI states or logs.

## Open Decisions

- Exact watchability model inputs (odds-only vs odds + team strength + game context).
- Auth simplification implementation choice (magic link vs other low-friction variants).
- Threshold for enabling multi-sport work (quality gate definition for NBA readiness).
