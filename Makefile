SHELL := /bin/sh
UV_CACHE_DIR ?= ./.cache/uv
UV_PROJECT_ENVIRONMENT ?= .venv-local
COMPOSE_FILE := infra/docker-compose.yml
ENV_FILE ?= .env
COMPOSE := docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE)
ESSENTIAL_ENV_VARS := API_HOST API_PORT POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_PORT VITE_API_BASE_URL

.PHONY: help setup up rebuild down reset logs test _test-api _test-worker _test-web _check-docker _check-env

help:
	@echo "Sports Alerts Platform"
	@echo ""
	@echo "  make setup      First-time local setup (.env + deps)"
	@echo "  make up         Start stack"
	@echo "  make rebuild    Rebuild images and start stack"
	@echo "  make down       Stop stack"
	@echo "  make reset      Stop stack and wipe volumes"
	@echo "  make logs       Tail logs (all services, or SERVICE=api)"
	@echo "  make test       Run API + worker + web checks"

setup:
	@if [ ! -f .env ]; then \
		printf '%s\n' \
			'APP_NAME=sports-alerts-api' \
			'API_HOST=0.0.0.0' \
			'API_PORT=8000' \
			'POSTGRES_USER=sports' \
			'POSTGRES_PASSWORD=sports' \
			'POSTGRES_DB=sports_alerts' \
			'POSTGRES_PORT=5432' \
			'DATABASE_URL=postgresql+psycopg://sports:sports@db:5432/sports_alerts' \
			'JWT_SECRET_KEY=replace-with-long-random-string' \
			'JWT_ALGORITHM=HS256' \
			'JWT_EXPIRE_MINUTES=86400' \
			'MAGIC_LINK_TTL_MINUTES=15' \
			'MAGIC_LINK_COOLDOWN_SECONDS=60' \
			'MAGIC_LINK_MAX_REQUESTS_PER_HOUR=5' \
			'WEB_BASE_URL=http://localhost:5173' \
			'CORS_ALLOW_ORIGINS=http://localhost:5173' \
			'ODDS_API_KEY=replace-with-the-odds-api-key' \
			'ODDS_API_BASE_URL=https://api.the-odds-api.com/v4/sports' \
			'ODDS_PROVIDER=the_odds_api' \
			'ODDS_API_SPORT_KEY=basketball_nba' \
			'ODDS_API_REGIONS=us' \
			'ODDS_API_MARKET=h2h' \
			'ODDS_API_FORMAT=american' \
			'ODDS_API_TIMEOUT_SECONDS=6' \
			'ODDS_API_CACHE_SECONDS=60' \
			'ODDS_ENABLED=true' \
			'ODDS_REFRESH_SECONDS=5400' \
			'DEV_MODE=false' \
			'NBA_PROVIDER=espn' \
			'DELIVERY_MODE=log' \
			'FROM_EMAIL=alerts@livegamealerts.com' \
			'RESEND_API_KEY=replace-with-resend-api-key' \
			'RESEND_API_URL=https://api.resend.com/emails' \
			'WORKER_POLL_INTERVAL_SECONDS=60' \
			'WORKER_POLL_INTERVAL_LIVE_SECONDS=30' \
			'WORKER_POLL_INTERVAL_SOON_SECONDS=120' \
			'WORKER_POLL_INTERVAL_DAY_SECONDS=300' \
			'WORKER_POLL_INTERVAL_IDLE_SECONDS=900' \
			'VITE_API_BASE_URL=http://localhost:8000' \
			> .env; \
		echo "Created .env with all required variables. Fill in real secret values."; \
	fi
	cd services/api && UV_PROJECT_ENVIRONMENT=$(UV_PROJECT_ENVIRONMENT) UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --group dev
	cd services/worker && UV_PROJECT_ENVIRONMENT=$(UV_PROJECT_ENVIRONMENT) UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --group dev
	cd apps/web && npm ci --include=optional

up:
	@$(MAKE) _check-docker
	@$(MAKE) _check-env
	$(COMPOSE) up -d

rebuild:
	@$(MAKE) _check-docker
	@$(MAKE) _check-env
	$(COMPOSE) up -d --build

down:
	@$(MAKE) _check-docker
	$(COMPOSE) down

reset:
	@$(MAKE) _check-docker
	$(COMPOSE) down -v --remove-orphans

logs:
	@$(MAKE) _check-docker
	$(COMPOSE) logs -f $(SERVICE)

test: _test-api _test-worker _test-web

_test-api:
	cd services/api && UV_PROJECT_ENVIRONMENT=$(UV_PROJECT_ENVIRONMENT) UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -q

_test-worker:
	cd services/worker && UV_PROJECT_ENVIRONMENT=$(UV_PROJECT_ENVIRONMENT) UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -q

_test-web:
	cd apps/web && npm ci --include=optional && npm run build

_check-docker:
	@command -v docker >/dev/null 2>&1 || { \
		echo "Docker CLI not found."; \
		echo "Install Docker Desktop: https://www.docker.com/products/docker-desktop/"; \
		exit 1; \
	}
	@docker compose version >/dev/null 2>&1 || { \
		echo "Docker Compose plugin not available."; \
		echo "Start Docker Desktop once, then re-run this command."; \
		exit 1; \
	}
	@docker info >/dev/null 2>&1 || { \
		echo "Docker daemon is not reachable."; \
		echo "Make sure Docker Desktop is running and retry."; \
		exit 1; \
	}

_check-env:
	@[ -f "$(ENV_FILE)" ] || { \
		echo "Missing $(ENV_FILE). Run 'make setup' first."; \
		exit 1; \
	}
	@for v in $(ESSENTIAL_ENV_VARS); do \
		grep -q "^$$v=" "$(ENV_FILE)" || { \
			echo "Missing $$v in $(ENV_FILE)."; \
			exit 1; \
		}; \
	done
