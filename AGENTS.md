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

Keep Alembic and use small, direct forward migrations. Migrations bring existing databases to the current schema; they do not require runtime support for old schemas. Ordinary deploys and restarts must preserve stored data.

Treat data according to whether it represents a user choice:

- Preserve accounts, authentication, team follows, alert preferences, push subscriptions, and league visibility/settings.
- Preserve team IDs and provider identities referenced by follows. Refresh team names, catalog membership, standings, and rankings in place; catalog reconciliation must not delete personal follows.
- Games, odds, standings, and derived alert history may be rebuilt when that makes a specific schema change simpler. Preserve or remap active game follows, unfollows, and per-game overrides before replacing referenced games. Normal expiration of games and their game-specific state under the existing retention policy is expected.

Choose the simplest path to the clean target schema:

- Use a straightforward forward migration when it reaches the target model directly.
- Prefer a targeted reset and reseed of regenerable sports data over complicated backfills, transitional code, compatibility columns, or a compromised target model. Do not reset the whole database for a sports-only change.
- Never retain an awkward schema merely to avoid rebuilding disposable data.
- Do not delete personal data or referenced identities unless the user has explicitly approved that loss. Permission to rebuild sports data is not permission to erase user choices.
- Keep the migration chain linear and compact. Retain applied revisions; squash only when there is a concrete maintenance benefit and a planned cutover that preserves personal data or explicitly approves its loss.
- Do not add reset commands, compatibility machinery, or export/import frameworks for hypothetical future schema changes.

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

The SQLite deployment uses one Render backend with a file-backed SQLite database on its persistent disk. Do not start a separate worker service, multiple Uvicorn processes, or replicas. Never put the live SQLite file on a network filesystem.

When production inspection is relevant, check Render CLI authentication first and initiate `render login` if needed. Do not request production authentication for local-only tasks.

Use SQLite's online backup API for live snapshots. Keep backups private, copy them off the service's disk, and stop the backend before restoring. See `docs/deployment.md` for schema changes, backups, and recovery.

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
