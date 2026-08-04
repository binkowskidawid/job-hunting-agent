# Job Hunting Agent

A personal agent that monitors job-posting sources, scores each offer against your CV and
your revealed preferences, and learns from how you rate what it shows you — without any
model fine-tuning.

## How it works

```text
sources (adapters) -> ingest & dedup -> scoring cascade -> Discord notification -> your rating
                                              ^                                          |
                                              +---------- preference learning <----------+
```

The scoring cascade is cost-first: a free rule-based filter, then free local vector
similarity, and only for genuinely uncertain offers, one paid LLM call. Every rating you give
feeds back into centroids, k-nearest-neighbor lookups, few-shot examples for the judge, and
periodically recalibrated thresholds.

An optional extension (see `CLAUDE.md`) adds a recruiter-message drafting agent with a real
tool-calling loop, persistent state, and a human-approval step — the only part of this
project that needs LangGraph.

## Quick start

```bash
git clone <this-repo>
cd job-hunting-app
cp .env.example .env   # fill in ANTHROPIC_API_KEY, DISCORD_BOT_TOKEN, etc.
docker compose up -d
```

This starts PostgreSQL (with `pgvector`), Ollama (local embeddings), and the app itself.

For local development without Docker:

```bash
uv sync
uv run pytest
```

## Status

Early development — most modules are currently stubs, with interfaces defined but not yet
implemented. See `CLAUDE.md` for the architecture and module map.

## License

MIT — see [LICENSE](./LICENSE).
