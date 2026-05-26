# Environment Variables

This repo uses strict env loading: if a required variable is missing, startup fails.

## Recommended `.env`

Keep one `.env` at repo root with this minimal set:

```env
POSTGRES_USER=sports
POSTGRES_PASSWORD=sports
POSTGRES_DB=sports_alerts
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://sports:sports@db:5432/sports_alerts

JWT_SECRET_KEY=replace-with-long-random-string
WEB_BASE_URL=http://localhost:5173
CORS_ALLOW_ORIGINS=http://localhost:5173

ODDS_API_KEY=replace-with-the-odds-api-key
# Local default: keep odds disabled to avoid spending API calls
ODDS_ENABLED=false
CATALOG_SYNC_INTERVAL_SECONDS=43200
NBA_LIVE_SYNC_INTERVAL_SECONDS=120
MLB_LIVE_SYNC_INTERVAL_SECONDS=300
LIVE_SYNC_PREGAME_RETRY_SECONDS=600
ODDS_API_SPORT_KEY_NBA=basketball_nba
ODDS_API_SPORT_KEY_MLB=baseball_mlb
ODDS_PREGAME_WINDOW_HOURS=24

RESEND_API_KEY=replace-with-resend-api-key

VITE_API_BASE_URL=http://localhost:8000

# Optional: Neon DB usage in Admin > DB Stats tab
NEON_API_KEY=replace-with-neon-api-key
NEON_PROJECT_ID=solitary-resonance-98873129
NEON_ORG_ID=org-empty-paper-73359802
NEON_DASHBOARD_URL=https://console.neon.tech/app/projects/solitary-resonance-98873129
```

## Notes

- `ODDS_ENABLED=false` is recommended for local development to avoid spending odds API calls.
- Worker sync defaults: shared catalog `12h`; NBA live `120s`; MLB live `300s`; pregame retry `600s`.
- Live sync updates scores/status only; odds refresh is handled by catalog sync pregame snapshots.
- `ODDS_API_KEY` is still required by strict settings even when odds are disabled. Use a placeholder value if disabled.
- Delivery defaults are in code (`email` mode, default sender), so only `RESEND_API_KEY` is required.
- Neon DB stats are shown only when `NEON_API_KEY` and `NEON_PROJECT_ID` are set.

## Service mapping

- API service needs API/auth/DB/cors/odds variables, plus delivery and magic-link settings.
- Worker service needs DB/provider/odds and sync cadence variables.
- Frontend service needs `VITE_API_BASE_URL`.

## Secrets policy

- Never commit secrets.
- Keep real values only in local `.env` and Render env settings.
- Use different secrets for local and deployed environments.
