# job-hunting-agent. `make help` lists available commands.
.DEFAULT_GOAL := help
COMPOSE := docker compose
# ON_ERROR_STOP is what makes a failed migration a failed target: without it psql reports the
# error, carries on to the next statement and exits 0.
PSQL = $(COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(POSTGRES_USER) -d $(POSTGRES_DB)

# Load .env if present so migrate/psql targets see POSTGRES_USER etc. Safe to omit on a
# fresh clone before `cp .env.example .env` — falls back to the .env.example defaults.
-include .env
export
POSTGRES_USER ?= job_agent
POSTGRES_DB ?= job_agent

.PHONY: help up down build logs ps pull-models \
	sync lint format typecheck test check migrate clean install-hooks

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' Makefile | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n",$$1,$$2}'

up: ## Start the stack, apply migrations and pull the embedding model — the one command
	$(COMPOSE) up -d --build postgres ollama app
	# `up -d` above returns as soon as containers are started, not once postgres is healthy —
	# force that wait explicitly so the steps below never race a cold Postgres.
	$(COMPOSE) up -d --wait postgres
	$(MAKE) migrate
	./scripts/ollama-pull-models.sh

down: ## Stop the stack (named volumes are kept)
	$(COMPOSE) down

build: ## Build images without starting containers
	$(COMPOSE) build

logs: ## Follow logs for all running containers
	$(COMPOSE) logs -f

ps: ## Show container status
	$(COMPOSE) ps

pull-models: ## Re-run the Ollama embedding-model pull (idempotent)
	./scripts/ollama-pull-models.sh

sync: ## Install/refresh local dependencies (fast lint/typecheck/test loop, no Docker)
	uv sync

lint: ## Run ruff (lint + format check)
	uv run ruff check .
	uv run ruff format --check .

typecheck: ## Run mypy in strict mode
	uv run mypy src tests

test: ## Run the test suite
	uv run pytest

check: lint typecheck test ## Run everything CI runs

migrate: ## Apply pending migrations, in order (idempotent — a ledger records what already ran)
	@$(PSQL) -q -f /migrations/002_schema_migrations.sql
	@for f in migrations/*.sql; do \
	  name=$$(basename "$$f"); \
	  applied=$$($(PSQL) -tAc "SELECT 1 FROM schema_migrations WHERE filename = '$$name'"); \
	  if [ -n "$$applied" ]; then \
	    echo "   skip  $$name"; \
	  else \
	    echo "-> apply $$name"; \
	    $(PSQL) -q -f "/$$f" || exit 1; \
	    $(PSQL) -qc "INSERT INTO schema_migrations (filename) VALUES ('$$name')"; \
	  fi; \
	done

clean: ## Stop the stack and DELETE named volumes (wipes Postgres data + pulled Ollama models)
	$(COMPOSE) down -v

install-hooks: ## Install the pre-commit hook (ruff on staged files)
	uv run pre-commit install
