SHELL := /bin/sh
REPO_ROOT := $(CURDIR)
BACKEND_DIR := services/backend
UV_CACHE_DIR ?= $(REPO_ROOT)/.cache/uv
UV_PROJECT_ENVIRONMENT ?= $(REPO_ROOT)/$(BACKEND_DIR)/.venv-local
UV_LINK_MODE ?= copy
COMPOSE_FILE := infra/docker-compose.yml
ENV_FILE ?= .env
COMPOSE := docker compose --env-file $(ENV_FILE) -f $(COMPOSE_FILE)
ESSENTIAL_ENV_VARS := WEB_BASE_URL CORS_ALLOW_ORIGINS JWT_SECRET_KEY RESEND_API_KEY VAPID_PUBLIC_KEY VAPID_PRIVATE_KEY VAPID_SUBJECT VITE_API_BASE_URL

.PHONY: help setup up rebuild down reset logs test web web-fix _lint-python _test-backend _test-web _check-docker _check-env

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
	@echo "  make test       Run backend + web checks"

setup:
	@if [ ! -f .env ]; then \
		printf '%s\n' \
			'JWT_SECRET_KEY=replace-with-long-random-string' \
			'WEB_BASE_URL=http://localhost:5173' \
			'CORS_ALLOW_ORIGINS=http://localhost:5173' \
			'ODDS_API_KEY=' \
			'RESEND_API_KEY=replace-with-resend-api-key' \
			'DELIVERY_MODE=log' \
			'VAPID_PUBLIC_KEY=' \
			'VAPID_PRIVATE_KEY=' \
			'VAPID_SUBJECT=mailto:you@example.com' \
			'VITE_API_BASE_URL=http://localhost:8000' \
			> .env; \
		echo "Created .env with all required variables. Fill in real secret values."; \
	fi
	cd $(BACKEND_DIR) && UV_PROJECT_ENVIRONMENT="$(UV_PROJECT_ENVIRONMENT)" UV_CACHE_DIR="$(UV_CACHE_DIR)" UV_LINK_MODE="$(UV_LINK_MODE)" uv sync --locked --group dev
	cd apps/web && npm ci --include=optional

up:
	@$(MAKE) _check-docker
	@$(MAKE) _check-env
	$(COMPOSE) up -d --remove-orphans

rebuild:
	@$(MAKE) _check-docker
	@$(MAKE) _check-env
	$(COMPOSE) up -d --build --remove-orphans

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

test: _lint-python _test-backend _test-web

_lint-python:
	UV_CACHE_DIR="$(UV_CACHE_DIR)" uvx --from ruff==0.16.3 ruff check --select E4,E7,E9,F $(BACKEND_DIR)/app $(BACKEND_DIR)/tests

_test-backend:
	cd $(BACKEND_DIR) && UV_PROJECT_ENVIRONMENT="$(UV_PROJECT_ENVIRONMENT)" UV_CACHE_DIR="$(UV_CACHE_DIR)" UV_LINK_MODE="$(UV_LINK_MODE)" uv run pytest -q tests

_test-web:
	cd apps/web && npm run format && npm run lint && npm test && VITE_API_BASE_URL=http://localhost:8000 npm run build

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
