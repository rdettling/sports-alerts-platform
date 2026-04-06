SHELL := /bin/sh
UV_CACHE_DIR ?= ./.cache/uv

.PHONY: help setup check-docker up down restart logs ps test test-api test-worker test-web build-web clean

help:
	@echo "Sports Alerts Platform commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup        Copy .env and install local dev deps"
	@echo ""
	@echo "Run:"
	@echo "  make up           Start full docker stack"
	@echo "  make down         Stop docker stack"
	@echo "  make restart      Restart docker stack"
	@echo "  make logs         Tail docker logs"
	@echo "  make ps           Show docker services"
	@echo ""
	@echo "Test:"
	@echo "  make test         Run API + worker tests + frontend build"
	@echo "  make test-api     Run API tests"
	@echo "  make test-worker  Run worker tests"
	@echo "  make test-web     Run frontend production build"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        Remove local Python virtualenvs"

setup:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	cd services/api && UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --group dev
	cd services/worker && UV_CACHE_DIR=$(UV_CACHE_DIR) uv sync --group dev
	cd apps/web && npm install

up:
	@$(MAKE) check-docker
	docker compose -f infra/docker-compose.yml up --build

down:
	@$(MAKE) check-docker
	docker compose -f infra/docker-compose.yml down

restart: down up

logs:
	@$(MAKE) check-docker
	docker compose -f infra/docker-compose.yml logs -f

ps:
	@$(MAKE) check-docker
	docker compose -f infra/docker-compose.yml ps

test: test-api test-worker test-web

test-api:
	cd services/api && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -q

test-worker:
	cd services/worker && UV_CACHE_DIR=$(UV_CACHE_DIR) uv run pytest -q

test-web:
	cd apps/web && npm run build

build-web: test-web

clean:
	rm -rf services/api/.venv services/worker/.venv

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
