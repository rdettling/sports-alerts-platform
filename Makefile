SHELL := /bin/sh
UV_CACHE_DIR ?= ./.cache/uv
UV_PROJECT_ENVIRONMENT ?= .venv-local
COMPOSE_FILE := infra/docker-compose.yml

.PHONY: help setup up rebuild down reset logs ps restart test test-api test-worker test-web check-docker

help:
	@echo "Sports Alerts Platform"
	@echo ""
	@echo "  make setup                    First-time local setup (.env + local deps for tests)"
	@echo "  make up                       Start stack from existing images"
	@echo "  make rebuild                  Rebuild images and start stack"
	@echo "  make down                     Stop stack"
	@echo "  make reset                    Stop stack and remove volumes"
	@echo "  make logs [SERVICE=api]       Tail logs (all services by default)"
	@echo "  make ps                       Show service status"
	@echo "  make restart SERVICE=api      Restart one service"
	@echo ""
	@echo "  make test                     Run all checks"
	@echo "  make test-api                 Run API tests"
	@echo "  make test-worker              Run worker tests"
	@echo "  make test-web                 Run frontend build"

setup:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	cd services/api && UV_PROJECT_ENVIRONMENT=$(UV_PROJECT_ENVIRONMENT) UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --group dev
	cd services/worker && UV_PROJECT_ENVIRONMENT=$(UV_PROJECT_ENVIRONMENT) UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --group dev
	cd apps/web && npm ci

up:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) up -d

rebuild:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) up -d --build

down:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) down

reset:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans

logs:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) logs -f $(SERVICE)

ps:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) ps

test: test-api test-worker test-web

test-api:
	cd services/api && UV_PROJECT_ENVIRONMENT=$(UV_PROJECT_ENVIRONMENT) UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -q

test-worker:
	cd services/worker && UV_PROJECT_ENVIRONMENT=$(UV_PROJECT_ENVIRONMENT) UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -q

test-web:
	cd apps/web && npm run build

restart:
	@$(MAKE) check-docker
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make restart SERVICE=api|worker|web|db"; \
		exit 1; \
	fi
	docker compose -f $(COMPOSE_FILE) restart $(SERVICE)

check-docker:
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
