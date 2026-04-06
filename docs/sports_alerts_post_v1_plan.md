# Sports Alerts Platform — Post-V1 Implementation Plan

## Summary

This plan starts from the current state:

- V1 milestones are complete.
- App is deployed (Render API + worker + static frontend, Neon Postgres).
- Delivery currently runs in `DELIVERY_MODE=log` (no real outbound email yet).

The goal of this next phase is to move from “working prototype” to “reliable production baseline” without overbuilding.

---

## Milestone 7 — Real Email Delivery (Resend)

### Goal
Enable real email delivery in production and keep reliable delivery tracking.

### Implementation
- Add Resend integration in worker delivery path.
- Keep existing `log` mode as fallback for local/dev.
- Add delivery config:
  - `DELIVERY_MODE=email|log`
  - `RESEND_API_KEY`
  - `FROM_EMAIL`
- Persist provider response metadata (`provider_message_id`, failure reason).
- Ensure failures set `delivery_status=failed` and never crash the loop.

### Acceptance criteria
- A test alert is received in real inbox from deployed app.
- `sent_alerts` rows show `delivery_status=sent` and provider message IDs.
- Invalid/missing API key results in failed status + clear logs, not worker crash.

---

## Milestone 8 — Reliability + Operations Hardening

### Goal
Improve run reliability and reduce production firefighting.

### Implementation
- Add structured JSON logging for API + worker (include service, env, request/ingest ids).
- Add worker retry/backoff for transient provider failures.
- Add stale-worker guardrail:
  - heartbeat log every cycle
  - alert if no successful ingest run for N minutes.
- Add simple rate limiting on auth endpoints (`/auth/login`, `/auth/register`).
- Add startup validation for required production env vars.

### Acceptance criteria
- Logs are easy to filter by service and event type.
- Temporary upstream outage recovers without manual restart.
- Auth abuse is limited by rate policy.

---

## Milestone 9 — Product UX Baseline (High-Value, Low-Complexity)

### Goal
Make the app more useful day-to-day without major architecture changes.

### Implementation
- Add “live now” and “starting soon” sections in games UI.
- Improve alert history UX:
  - filter by alert type
  - last 24h / 7d quick filter
  - clearer status badges.
- Add “test alert” button in preferences (calls worker/email path safely).
- Add empty/error/loading states consistency pass across all tabs.

### Acceptance criteria
- User can quickly see which games matter now.
- User can verify email configuration from UI.
- History view is usable without scrolling through unfiltered rows.

---

## Milestone 10 — Security + Data Safety

### Goal
Close obvious security/data gaps for a real hosted service.

### Implementation
- Force secure JWT secret policy (length/entropy check in production).
- Add password policy floor and clear validation messages.
- Add account-level lockout/cooldown after repeated failed logins.
- Add DB backup/restore runbook and verify restore once.
- Add secret hygiene checks in CI (gitleaks or equivalent).

### Acceptance criteria
- Security controls are active and tested.
- Backup restore is documented and successfully exercised once.
- CI blocks committed secrets.

---

## Milestone 11 — Test and CI Expansion

### Goal
Increase confidence in deploys while keeping CI fast.

### Implementation
- Add API tests for rate-limit and auth lockout behavior.
- Add worker tests for email delivery success/failure paths.
- Add one deployed smoke test script:
  - health check
  - register/login
  - follow flow
  - history fetch.
- Add GitHub Actions workflow for `make test` on PR.

### Acceptance criteria
- PR checks block regressions on core flows.
- Email-path behavior is covered by automated tests.
- Smoke script catches obvious deploy breaks quickly.

---

## Milestone 12 — Deployment and Cost Discipline

### Goal
Keep the service reliable and cheap as usage grows.

### Implementation
- Document current production topology and scaling knobs.
- Set Render alerts for failed deploys and unhealthy service.
- Tune worker polling defaults for cost vs freshness.
- Add monthly operations checklist (cost, error rates, delivery success).

### Acceptance criteria
- Cost and reliability are reviewed on a recurring cadence.
- Team can diagnose incidents from docs + logs without guesswork.

---

## Public Interfaces / Contracts to Add

- Worker delivery provider contract for Resend integration.
- Optional API endpoint for test alert trigger (authenticated).
- Optional query params for alert history filtering.

---

## Assumptions

- Single production environment is kept for now (no separate staging).
- Render + Neon remains the deployment target.
- Resume value and practical reliability are prioritized over feature breadth.
- NFL/multi-league support is deferred until after email + reliability hardening.

---

## Suggested Execution Order

1. Milestone 7 (real email)  
2. Milestone 8 (ops hardening)  
3. Milestone 11 (CI/test expansion)  
4. Milestone 9 (UX baseline)  
5. Milestone 10 + 12 (security/cost discipline)
