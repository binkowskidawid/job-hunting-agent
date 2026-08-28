# Contributing

Thank you for your interest in contributing! This document covers everything you need to
get started.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](./CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

1. Search existing issues first — your bug may already be reported.
2. Open a new issue using the **Bug Report** template.
3. Include: OS, Python version, Docker version, and exact error output.

### Suggesting Features

1. Open a new issue using the **Feature Request** template.
2. Explain the problem you are solving, not just the solution.

### Submitting a Pull Request

1. **Fork** the repository and create a branch from `main`:

   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Start the dev stack:**

   ```bash
   make up
   ```

3. **Install dependencies locally** (for fast lint/typecheck/test without the full stack):

   ```bash
   make sync
   ```

4. **Make your changes.** Follow the code standards below.

5. **Run checks before pushing** (mirrors CI exactly):

   ```bash
   make check
   ```

   > The pre-commit hook (`make install-hooks`) runs ruff automatically on staged files —
   > `make check` above is a full-repo sanity check. Run `make help` to see every command.

6. **Commit** using Conventional Commits:

   ```text
   feat(scoring): add manipulation-detection field to judge schema
   fix(ingest): handle multilocation duplicates correctly
   docs(readme): update quick start steps
   ```

7. Open a Pull Request against `main`.

## Code Standards

- **Python 3.14+**, type hints everywhere — `mypy --strict` must pass.
- **No bare `except:`** — catch specific exceptions.
- **Pydantic models** at every data boundary (LLM output, config files, API payloads).
- **Async/await** for all IO — no blocking calls in async code paths.
- **Max function length** — 40 lines. Split if longer.
- **No magic numbers** — use named constants.
- **LLM calls** go through `LLMClient.structured()` only — never call the Anthropic SDK
  directly from feature code.

## Project Structure

All application code lives under `src/`, as flat packages (no wrapper package name) — see
`AGENTS.md` for why. `tests/`, `prompts/`, and `migrations/` stay at the repo root.

| Directory | Purpose |
| --- | --- |
| `src/domain/` | Core data models (e.g. `Offer`) shared across the whole pipeline |
| `src/sources/` | Adapters for job-posting sources — one class per source |
| `src/ingest/` | Deduplication and source health monitoring |
| `src/candidate/` | Hand-written competency profile and hard filters |
| `src/scoring/` | The cost-aware scoring cascade (filter -> similarity -> LLM judge) |
| `src/learning/` | Preference learning: centroids, calibration, exploration, drift detection |
| `src/discord_bot/` | The rating UI |
| `src/orchestration/` | Scheduling and the ingest cycle |
| `src/extension/`, `src/tools/`, `src/api/` | Optional recruiter-message-drafting extension |
| `src/evals/` | Golden-set tests and manual rejection audits |

## Questions?

Open a discussion — happy to help.
