# Agent Guidance

This is a personal project repo. The highest priority is keeping the codebase clean, compact, and easy for Codex or any other coding agent to understand in limited context.

Treat the repo as something that should stay continuously maintainable, not something that accumulates complexity and needs periodic rescue cleanup.

## Core Principle

Optimize for long-term code clarity over preserving accidental structure.

Good changes should make the repo easier to read, reason about, test, and modify. Avoid leaving behind code that a future agent will need to untangle.

## Default Posture

- Preserve intended user-facing behavior unless the user asks otherwise.
- Prefer simple, direct code over abstractions, indirection, generalized patterns, or speculative extensibility.
- Keep the codebase small. Delete dead code, unused options, stale comments, duplicate helpers, and unnecessary configuration when it is safe.
- Favor cohesive modules and obvious data flow over many tiny wrappers or layers.
- Do not introduce new dependencies unless they clearly reduce more complexity than they add.
- Do not add knobs, flags, environment variables, or extension points for hypothetical future needs.
- When touching an area, leave it cleaner than you found it.

## Personal Project Assumptions

- This repo is optimized for one developer moving quickly with coding agents.
- Clean code and low maintenance burden matter more than enterprise-style flexibility.
- Avoid patterns that only pay off for larger teams, multiple tenants, plugin ecosystems, or uncertain future scale.
- Prefer boring, explicit implementation choices that are easy to inspect in one pass.

## Data And Schema Evolution

Optimize for the clean current schema, not compatibility with historical schema shapes. The application supports only the latest Alembic revision; do not add runtime compatibility layers, dual reads or writes, deprecated columns, or old and new API shapes.

Production sports-domain data is disposable. Games, odds, game-related follows, alert history, and similar derived state may be reset or regenerated when that produces a simpler design.

Choose the simplest path to the clean target schema:

- Use a straightforward forward migration when it reaches the target model directly, especially when it preserves user identity, authentication, preferences, or other difficult-to-recreate data.
- Prefer reset and reseed when preserving disposable sports data would require complicated backfills, transitional code, compatibility columns, or a compromised target model.
- Never retain an awkward schema merely to avoid a destructive migration.
- Do not destructively reset user or authentication data unless the user has explicitly approved that tradeoff.
- Keep the migration chain linear and compact. It may be deliberately squashed into a new baseline when migration history becomes a maintenance burden and the corresponding reset or cutover has been planned.
- Do not rewrite an already-applied migration casually; use a new direct migration or an explicitly planned baseline reset.

## Avoid Creating Cleanup Debt

Before adding code, ask whether a future cleanup prompt would likely delete it. If yes, choose the simpler design now.

Avoid:

- New abstractions with only one caller.
- Generic frameworks around simple workflows.
- Defensive code for states the app cannot realistically enter.
- Large helper files that hide simple logic.
- Duplicated types or schemas that drift from each other.
- Configuration options that are not actively used.
- Comments that explain what the code already says.

Prefer:

- Inline logic when it is clearer than naming a helper.
- Small focused helpers when they remove real repetition.
- Clear names over comments.
- Direct database queries over elaborate repository layers.
- A small number of obvious files over deeply nested structure.
- Tests that lock behavior without over-specifying implementation.

## Operational Reality

The database is a constrained resource. Worker and background code should avoid unnecessary polling, retries, writes, long-lived connections, and noisy failure loops.

Operational observability is useful only when it helps debug real issues. Keep telemetry and admin tooling compact; avoid high-volume or open-ended logging/storage without a clear use.

## Production Access

This repo often uses the Render CLI and Neon CLI for production inspection.

When a task may involve production logs, deploy state, runtime debugging, or production database inspection:

- First check whether Render CLI and Neon CLI are already authenticated.
- If Render auth is missing or expired, run `render login` so the browser or device authorization flow opens for the user.
- If Neon auth is missing, initiate the Neon login flow rather than asking the user to type auth commands manually.
- Prefer setting up CLI auth proactively once production access is relevant, instead of waiting for a failed command later.
- Do not ask the user to authenticate up front for tasks that do not require production access.

## Verification

Run the narrowest relevant checks for the area changed, then broaden when the touched behavior is shared. If checks cannot be run, state that clearly and explain the residual risk.

Docs-only changes usually do not need tests.

## Git Workflow

This is a single-developer personal repository.

- Never commit implementation work directly to `main`.
- Keep work on the currently checked-out working branch unless the user explicitly asks to switch or create a branch.
- When asked to commit or push, use the current working branch and its corresponding remote branch unless the user specifies another target.
- Do not open pull requests. When explicitly asked to integrate completed work, squash-merge the working branch into `main` locally so `main` receives one cohesive commit.
- Do not merge, push, or delete branches unless the user asks for that action.
- Before committing, confirm the current branch is not `main`, verify the worktree contains only the intended changes, and run the relevant checks.

## Working Style

- Check the worktree before editing and do not revert unrelated user changes.
- Make substantial changes only within one cohesive theme at a time.
- Stop before drifting into unrelated cleanup.
- Summarize what changed, why it is cleaner, and what was verified.
