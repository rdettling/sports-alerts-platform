SHELL := /bin/sh
REPO_ROOT := $(CURDIR)
BACKEND_DIR := services/backend
UV_CACHE_DIR ?= $(REPO_ROOT)/.cache/uv
UV_PROJECT_ENVIRONMENT ?= $(REPO_ROOT)/$(BACKEND_DIR)/.venv-local
UV_LINK_MODE ?= copy
COMPOSE_FILE := infra/docker-compose.yml
ENV_FILE ?= .env
COMPOSE := docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE)
ESSENTIAL_ENV_VARS := POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB POSTGRES_PORT DATABASE_URL JWT_SECRET_KEY ODDS_API_KEY RESEND_API_KEY VAPID_PUBLIC_KEY VAPID_PRIVATE_KEY VAPID_SUBJECT VITE_API_BASE_URL

.PHONY: help setup up rebuild down reset logs test web web-fix _lint-python _test-api _test-worker _test-web _check-docker _check-env

help:
	@echo "Sports Alerts Platform"
	@echo ""
	@echo "  make setup      First-time local setup (.env + deps)"
	@echo "  make up         Start stack"
	@echo "  make rebuild    Rebuild images and start stack"
	@echo "  make down       Stop stack"
	@echo "  make reset      Stop stack and wipe volumes"
	@echo "  make logs       Tail logs (all services, or SERVICE=api)"
	@echo "  make web        Recreate only web service"
	@echo "  make web-fix    Repair web node_modules and recreate web"
	@echo "  make test       Run API + worker + web checks"

setup:
	@if [ ! -f .env ]; then \
		printf '%s\n' \
			'POSTGRES_USER=sports' \
			'POSTGRES_PASSWORD=sports' \
			'POSTGRES_DB=sports_alerts' \
			'POSTGRES_PORT=5432' \
			'DATABASE_URL=postgresql+psycopg://sports:sports@db:5432/sports_alerts' \
			'JWT_SECRET_KEY=replace-with-long-random-string' \
			'WEB_BASE_URL=http://localhost:5173' \
			'CORS_ALLOW_ORIGINS=http://localhost:5173' \
			'ODDS_API_KEY=replace-with-the-odds-api-key' \
			'ODDS_ENABLED=false' \
			'RESEND_API_KEY=replace-with-resend-api-key' \
			'DELIVERY_MODE=log' \
			'VAPID_PUBLIC_KEY=' \
			'VAPID_PRIVATE_KEY=' \
			'VAPID_SUBJECT=mailto:you@example.com' \
			'CATALOG_SYNC_INTERVAL_SECONDS=43200' \
			'ODDS_PREGAME_WINDOW_HOURS=24' \
			'VITE_API_BASE_URL=http://localhost:8000' \
			> .env; \
		echo "Created .env with all required variables. Fill in real secret values."; \
	fi
	cd $(BACKEND_DIR) && UV_PROJECT_ENVIRONMENT="$(UV_PROJECT_ENVIRONMENT)" UV_CACHE_DIR="$(UV_CACHE_DIR)" UV_LINK_MODE="$(UV_LINK_MODE)" uv sync --locked --group dev
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

web:
	@$(MAKE) _check-docker
	@$(MAKE) _check-env
	$(COMPOSE) up -d --force-recreate web

web-fix:
	@$(MAKE) _check-docker
	@$(MAKE) _check-env
	$(COMPOSE) run --rm --entrypoint "" web npm ci --include=optional
	$(COMPOSE) up -d --force-recreate web

test: _lint-python _test-api _test-worker _test-web

_lint-python:
	UV_CACHE_DIR="$(UV_CACHE_DIR)" uvx --from ruff==0.16.3 ruff check --select E4,E7,E9,F $(BACKEND_DIR)/app $(BACKEND_DIR)/worker $(BACKEND_DIR)/tests

_test-api:
	cd $(BACKEND_DIR) && UV_PROJECT_ENVIRONMENT="$(UV_PROJECT_ENVIRONMENT)" UV_CACHE_DIR="$(UV_CACHE_DIR)" UV_LINK_MODE="$(UV_LINK_MODE)" uv run pytest -q tests/api

_test-worker:
	cd $(BACKEND_DIR) && UV_PROJECT_ENVIRONMENT="$(UV_PROJECT_ENVIRONMENT)" UV_CACHE_DIR="$(UV_CACHE_DIR)" UV_LINK_MODE="$(UV_LINK_MODE)" uv run pytest -q tests/worker

_test-web:
	cd apps/web && npm ci --include=optional && npm run format && npm run lint && npm test && npm run build

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
