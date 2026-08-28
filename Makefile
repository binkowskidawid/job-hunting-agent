# job-hunting-agent. `make help` lists available commands.
.DEFAULT_GOAL := help
COMPOSE := docker compose

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

up: ## Build and start postgres, ollama, app, then pull the embedding model
	$(COMPOSE) up -d --build postgres ollama app
	# `up -d` above returns as soon as containers are started, not once postgres is healthy —
	# force that wait explicitly so the pull-models step below never races a cold Postgres.
	$(COMPOSE) up -d --wait postgres
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

migrate: ## Apply all migrations/*.sql against the running postgres container, in order
	@for f in migrations/*.sql; do \
	  echo "-> applying $$f"; \
	  $(COMPOSE) exec -T postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB) -f "/$$f" || exit 1; \
	done

clean: ## Stop the stack and DELETE named volumes (wipes Postgres data + pulled Ollama models)
	$(COMPOSE) down -v

install-hooks: ## Install the pre-commit hook (ruff on staged files)
	uv run pre-commit install
