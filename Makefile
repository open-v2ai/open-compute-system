.DEFAULT_GOAL := help

.PHONY: help install deps migrate dev-api dev-agent dev-worker dev-scheduler dev-web \
	generate-client test test-api test-agent check check-api check-agent check-web build \
	build-agent build-all start stop open-source-check

help:
	@echo "Open Compute System development commands"
	@echo "  make install            Install API, agent, and web dependencies"
	@echo "  make dev-api            Start the local API on 127.0.0.1:8000"
	@echo "  make dev-web            Start the local web app on 127.0.0.1:3000"
	@echo "  make check              Run API, agent, and web static checks"
	@echo "  make test               Run API, agent, and web tests"
	@echo "  make build              Build the Next.js application"
	@echo "  make generate-client    Regenerate the frontend OpenAPI contract"
	@echo "  make open-source-check  Check repository hygiene and local doc links"

install:
	cd api && uv sync --frozen
	cd agent && uv sync --frozen
	cd web && pnpm install --frozen-lockfile

migrate:
	cd api && uv run --frozen python scripts/upgrade_database.py

deps:
	docker compose -f deploy/compose.local.yaml up -d

dev-api:
	cd api && uv run --frozen uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-agent:
	cd agent && uv run --frozen uvicorn app.main:app --reload --host 127.0.0.1 --port 8110

dev-worker:
	cd api && uv run --frozen celery -A app.workers.celery_app.celery_app worker --loglevel=INFO

dev-scheduler:
	cd api && uv run --frozen celery -A app.workers.celery_app.celery_app beat --loglevel=INFO

dev-web:
	cd web && pnpm dev

generate-client:
	cd api && uv run --frozen python scripts/generate_openapi.py

test: test-api test-agent
	cd web && pnpm test

test-api:
	cd api && uv run --frozen pytest -q

test-agent:
	cd agent && uv run --frozen pytest -q

check: check-api check-agent check-web

check-api:
	cd api && uv run --frozen ruff check .

check-agent:
	cd agent && uv run --frozen ruff check app tests

check-web:
	cd web && pnpm typecheck && pnpm lint && pnpm test

build:
	cd web && pnpm build

open-source-check:
	python3 scripts/check_open_source.py

DEPENDENCIES ?= bundled
INGRESS ?= container
DEPLOY_ENV ?= deploy/.env
DEPLOY_FLAGS ?=
DEPLOY_COMPOSE = python3 deploy/compose.py --dependencies $(DEPENDENCIES) --ingress $(INGRESS) --env-file $(DEPLOY_ENV) $(DEPLOY_FLAGS)

build-all:
	$(DEPLOY_COMPOSE) build api web

build-agent:
	docker compose --env-file deploy/.env -f deploy/compose.agent.yaml build

start:
	$(DEPLOY_COMPOSE) up -d

stop:
	$(DEPLOY_COMPOSE) down
