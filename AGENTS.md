# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Copilot, Cursor, or any other
tool that reads `AGENTS.md`) when working with code in this repository.

## Essential Commands

```bash
# Build and start the full stack (Postgres+pgvector, Ollama, the app) and pull the
# embedding model into Ollama — the one command a fresh clone needs
make up

# Run a one-off command inside the app container
docker compose exec app uv run pytest

# Fast local loop (no Docker needed for lint/typecheck/test)
make sync
make check          # lint + typecheck + test, mirrors CI exactly

# See every available command
make help
```

## Architecture Overview

A single-user Python agent with four stages:

1. **Ingest** — pluggable source adapters (`src/sources/`) normalize job postings into a
   common `Offer` schema (`src/domain/offer.py`), deduplicated three ways
   (`src/ingest/dedup.py`).
2. **Scoring cascade** (`src/scoring/`) — cheapest signal first: a free rule-based filter,
   then free local vector similarity + k-NN against your own ratings, and only for offers in
   the uncertain zone, one paid LLM judge call.
3. **Notification** (`src/discord_bot/`) — a Discord card with one-tap rating buttons
   (great/maybe/pass/never_again).
4. **Learning** (`src/learning/`) — every rating updates weighted, time-decayed centroids and
   shifts the signal weights as the rating count grows (`weights_for_stage`). Threshold
   recalibration, few-shot example refresh and exploration are out of scope for v0.1; see
   [Scope](#scope).

**Code layout:** all application code lives flat under `src/` (`src/domain/`,
`src/scoring/`, ...) — no wrapper package, nothing built or installed. `pyproject.toml` sets
`[tool.uv] package = false`; `pythonpath = ["src"]` (pytest) and `mypy_path = "src"` (mypy)
make every package importable by its bare name (`from domain.offer import Offer`) without
installing anything. `tests/`, `prompts/`, and `migrations/` stay at the repo root.

**Tech stack:** Python 3.14, PostgreSQL + pgvector, Ollama (local embeddings), Anthropic API
(LLM judge), discord.py, APScheduler.

## Core Modules

| Path | Purpose |
| --- | --- |
| `src/domain/` | `Offer` — the schema every source adapter and every downstream stage shares |
| `src/sources/` | One `Adapter` subclass per data source, each declaring a legal/ethical `basis` |
| `src/ingest/` | Deduplication (`identity_key`, `save`) |
| `src/candidate/` | Hand-written `profile.yaml` (competencies) + hand-edited `filters.yaml` (thresholds) |
| `src/scoring/` | The cascade: `filter.py` -> `similarity.py` -> `decision.py` -> `judge.py`, glued by `cascade.py` |
| `src/learning/` | Cold-start weights and weighted, time-decayed centroids |
| `src/discord_bot/` | Rating UI |
| `src/orchestration/` | Scheduler and the idempotent ingest cycle |
| `src/db.py` | The only path to Postgres — one async connection pool, never a fresh connection |
| `src/llm_client.py` | The only path to the Anthropic API — forced structured output, cost tracking, prompt caching |
| `src/main.py` | Process entrypoint (what `docker compose up app` runs) |

## Scope

v0.1 is one vertical slice that runs end to end: RSS/Atom ingest → dedup → rule filter →
local vector similarity → decision → LLM judge for the uncertain zone → Discord card →
rating → centroid update. Everything in `src/` is implemented; there are no stubs on `main`.

Deliberately **out of scope** for v0.1. Do not add these back without being asked — each one
was cut for the reason given, and the scaffold code for it is recoverable with
`git show v0.0-scaffold:src/<path>`:

| Cut | Why | Comes back when |
| --- | --- | --- |
| `sources/email_alert.py`, `sources/generic_api.py` | each needs its own legal basis established first | `SOURCES.md` audit covers it |
| `learning/calibration.py` | recalibrating thresholds against <100 ratings overfits to noise | ~100 ratings exist |
| `learning/examples.py` | few-shot examples for the judge need rated offers to draw from | ~100 ratings exist |
| `learning/exploration.py` | there is no filter bubble to escape before the filter has a history | thresholds are calibrated |
| `ingest/monitor.py` | source health monitoring is meaningless with one source | a second source exists |
| `multi_cluster_centroids()` | one centroid is enough until ratings visibly split into clusters | clusters appear in the data |
| `extension/`, `api/`, `tools/` | recruiter-message drafting is a separate product with its own risks | its own release |

## Development Patterns

- **Adapter pattern**: every source is an `Adapter` subclass with `name`, `basis`,
  `min_interval_s`, and async `fetch() -> list[Offer]`. Adding a source never touches the rest
  of the system.
- **Structured output only**: every LLM call goes through `LLMClient.structured()`, which
  forces `tool_choice` — never parse free-form text as JSON.
- **Cascade cost ordering**: cheapest signal first. If you're tempted to call the LLM earlier
  in the pipeline, that's a signal the cheaper stages need better features, not that the LLM
  should move up.
- **Config over code**: business thresholds (salary minimums, stop words, tech vetoes) live in
  `src/candidate/filters.yaml`, never hardcoded in Python — this makes them git-diffable
  decisions.
- **Provenance**: any model-produced field that drives a decision (the judge verdict) carries
  a confidence and/or a verbatim source quote. The competency profile is hand-written, so it
  needs none — you are its source.

## Testing Strategy

- `pytest` + `pytest-asyncio`. The reference set under `eval/` (real offers, recorded
  embeddings, recorded judge responses) drives both `make demo` and the cascade regression
  test: each offer carries a hand-written expected rejection stage, not an expected score,
  since temperature 0 does not mean deterministic output.
- New source adapters need a fixture test against a saved real response — catch a broken
  parser before you notice a week of silence.

## Database Migrations

Plain, numbered SQL files in `migrations/` at the repo root (`001_init.sql`, `002_...sql`,
...). Apply all pending migrations with `make migrate`, or by hand via `docker compose exec
postgres psql -U job_agent -d job_agent -f /migrations/00N_name.sql`. Never edit an
already-applied migration — add a new one.

## Critical Implementation Notes

1. **The model never computes final scores, salary math, or thresholds.** It extracts,
   classifies, and judges; arithmetic and business rules live in Python.
2. **Every offer rejection (filter or cascade) is persisted with a reason.** This is the only
   way to audit false negatives later.
3. **Notification sends are idempotent**, enforced by a database `UNIQUE` constraint — never
   by an application-level check alone.
4. **Never give the agent a tool that can send an application or contact a recruiter.**
   Anything the project ever drafts is drafted only; a human sends it.
5. **Job-posting content is untrusted input.** Keep it in the user turn, wrapped in a clearly
   labeled `<JOB_POSTING>` tag, never concatenated into the system prompt.

## Engineering Rules

### Scope and verification

- Make the smallest change that solves the requested problem. Do not refactor adjacent code.
- Reuse existing adapters, models, and utilities before adding new ones.
- Validate changes with `make lint`, `make typecheck`, and focused `pytest` for the affected
  area (`make check` runs everything).

### Python and code organisation

- Type hints everywhere; `mypy --strict` must pass. No `Any` without a comment explaining why.
- No bare `except:` — catch specific exceptions.
- Pydantic models at every data boundary (LLM output, config files, API payloads).
- Do not add code comments that explain *what* the code does — only *why*, when non-obvious.
- All application code lives under `src/`, flat (no wrapper package) — never create a new
  top-level directory outside `src/` for importable Python.

### Data and performance

- No database queries inside loops — batch fetch, map in memory.
- Use connection pooling (`asyncpg`/`psycopg` async pool), never a fresh connection per call.
- Use `asyncio.gather` for independent concurrent reads.

### LLM and cost

- All LLM calls go through `LLMClient.structured()` — never call the Anthropic SDK directly.
- Every call logs `cost_usd`; never skip logging "to save time" on a prototype.
- Any tool-calling loop must have all three stop conditions: max iterations, max cost, and a
  terminal "save" tool — never rely on the model stopping on its own.
- Never hand-type a model price or a package version — pricing must be checked against the
  current provider page before being written into code; package versions come from `uv add`.

### Logging

- Use the `logging` module, not `print()`, outside of one-off scripts.
- Never log CV content, API keys, Discord tokens, or full prompt text at INFO level.

### Git

- Do not run state-changing git operations (commit, push, checkout, branch, reset, merge,
  rebase) unless explicitly requested. Read-only commands (status, log, diff) are fine.

### Accuracy and uncertainty

- Never invent package versions, API behaviour, pricing, or repository conventions.
- Verify claims against the current repository, command output, or authoritative
  documentation before presenting them as fact.
- State uncertainty explicitly rather than guessing.

## Developer Tools

- Use `uv` for everything — never `pip install` or `poetry` directly in this repo.
- Python 3.14+.
- `make help` lists the Docker Compose and local-dev shortcuts; prefer them over hand-typed
  `docker compose`/`uv run` invocations for anything already covered.

## graphify

*This section is added once `graphify` has been run against real (non-stub) code — a
knowledge graph over stub-only modules has nothing useful to index yet.*
