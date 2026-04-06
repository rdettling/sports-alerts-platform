# Local Development

## Prerequisites

- Docker Desktop
- `uv`
- Node.js 20+

## Setup

1. `make setup`
2. Edit `.env` and set `JWT_SECRET_KEY`
3. `make rebuild`

## Useful Commands

- `make up`
- `make down`
- `make reset` (destructive: removes DB volume)
- `make logs`
- `make logs SERVICE=api`
- `make ps`
- `make restart SERVICE=worker`
- `make test`

## Common Debug Checks

- API health: `http://localhost:8000/healthz`
- API docs: `http://localhost:8000/docs`
- If web says API unreachable, confirm `VITE_API_BASE_URL` and API logs.
