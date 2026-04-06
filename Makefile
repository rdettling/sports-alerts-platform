SHELL := /bin/sh
UV_CACHE_DIR ?= ./.cache/uv
COMPOSE_FILE := infra/docker-compose.yml

.PHONY: help setup up down logs restart-api restart-worker restart-web test test-api test-worker test-web check-docker

help:
	@echo "Sports Alerts Platform"
	@echo ""
	@echo "  make setup          First-time setup (env + deps)"
	@echo "  make up             Start stack in background"
	@echo "  make logs           Tail all service logs"
	@echo "  make down           Stop stack"
	@echo ""
	@echo "  make restart-api    Restart API service"
	@echo "  make restart-worker Restart worker service"
	@echo "  make restart-web    Restart frontend service"
	@echo ""
	@echo "  make test           Run all checks"
	@echo "  make test-api       Run API tests"
	@echo "  make test-worker    Run worker tests"
	@echo "  make test-web       Run frontend build"

setup:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	cd services/api && UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --group dev
	cd services/worker && UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --group dev
	cd apps/web && npm install

up:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) up -d --build

down:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) down

logs:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) logs -f

test: test-api test-worker test-web

test-api:
	cd services/api && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -q

test-worker:
	cd services/worker && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -q

test-web:
	cd apps/web && npm run build

restart-api:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) restart api

restart-worker:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) restart worker

restart-web:
	@$(MAKE) check-docker
	docker compose -f $(COMPOSE_FILE) restart web

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
