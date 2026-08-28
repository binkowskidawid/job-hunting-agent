<div align="center">
  <h1>Job Hunting Agent</h1>
  <p><strong>A personal agent that scores job postings against your CV and learns from your ratings — no fine-tuning required.</strong></p>
  <p>
    <a href="https://github.com/binkowskidawid/job-hunting-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License" /></a>
    <a href="https://github.com/binkowskidawid/job-hunting-agent/actions"><img src="https://img.shields.io/github/actions/workflow/status/binkowskidawid/job-hunting-agent/ci.yml?label=CI" alt="CI" /></a>
    <img src="https://img.shields.io/badge/python-3.14%2B-3776ab" alt="Python" />
    <img src="https://img.shields.io/badge/uv-package%20manager-de5fe9" alt="uv" />
    <img src="https://img.shields.io/badge/postgres-pgvector-336791" alt="PostgreSQL + pgvector" />
    <img src="https://img.shields.io/badge/ollama-local%20embeddings-000000" alt="Ollama" />
  </p>
</div>

---

Job Hunting Agent watches your chosen job-posting sources, scores every offer against your
profile and your revealed preferences, and gets better over time from a single tap on a
Discord notification — great, maybe, pass, or never again. No model fine-tuning: the weights
behind the decision shift as your ratings accumulate.

## ✨ Features

- 🔌 **Pluggable sources** — every source is an `Adapter` subclass declaring its own legal/ethical `basis`; adding one never touches the rest of the pipeline
- 💸 **Cost-first scoring cascade** — free rule-based filter → free local vector similarity + k-NN against your own ratings → one paid LLM judge call, only for offers in the uncertain zone
- 🔔 **One-tap Discord ratings** — a card per offer with `great` / `maybe` / `pass` / `never_again` buttons, idempotent sends enforced at the database level
- 🧠 **Learning from ratings** — every rating updates weighted, time-decayed centroids, and the signal weights shift as the rating count grows, so the system leans on your CV on day one and on your revealed preferences later
- 🐳 **One-command self-hosting** — `make up` builds Postgres+pgvector, Ollama, and the app, then pulls the embedding model automatically

## 🏗️ Architecture

```text
sources (adapters) -> ingest & dedup -> scoring cascade -> Discord notification -> your rating
                                              ^                                          |
                                              +---------- preference learning <----------+
```

Every stage is cheapest-signal-first: if a cheaper stage could catch what the LLM currently
catches, that's a signal to improve the cheaper stage — not to move the LLM earlier.

## 🛠️ Tech Stack

| Layer | Technology | Notes |
| ------------------ | -------------------------- | ----------------------------------- |
| Language | Python | 3.14+ |
| Package manager | uv | `[tool.uv] package = false` — flat `src/`, nothing installed |
| Database | PostgreSQL + pgvector | 0.8.6 (pg18) |
| Local embeddings | Ollama | `nomic-embed-text` |
| LLM judge | Anthropic API | via a single `LLMClient.structured()` gate |
| Notifications | discord.py | rating buttons, idempotent sends |
| Scheduling | APScheduler | idempotent ingest cycle |

## 📁 Project Structure

```text
job-hunting-agent/
├── src/
│   ├── domain/          # Offer — the schema every adapter and stage shares
│   ├── sources/         # One Adapter subclass per data source
│   ├── ingest/          # Deduplication
│   ├── candidate/       # Hand-written profile.yaml + hand-edited filters.yaml
│   ├── scoring/         # filter.py -> similarity.py -> decision.py -> judge.py, glued by cascade.py
│   ├── learning/        # Cold-start weights and weighted, time-decayed centroids
│   ├── discord_bot/     # Rating UI
│   ├── orchestration/   # Scheduler and the idempotent ingest cycle
│   ├── db.py            # The only path to Postgres — one async pool
│   └── llm_client.py    # The only path to the Anthropic API
├── eval/                 # Reference set: real offers + recorded responses (drives `make demo`)
├── tests/
├── prompts/
├── migrations/           # Plain, numbered SQL files (001_init.sql, ...)
├── docker-compose.yml
├── Dockerfile
└── Makefile
```

See [AGENTS.md](./AGENTS.md) for the full module map and engineering rules.

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose v2
- [uv](https://docs.astral.sh/uv/) (for local dev without Docker)

### 1. Clone & configure

```bash
git clone https://github.com/binkowskidawid/job-hunting-agent.git
cd job-hunting-agent
cp .env.example .env   # fill in ANTHROPIC_API_KEY, DISCORD_BOT_TOKEN, etc.
```

### 2. Start the stack

```bash
make up
```

This builds and starts PostgreSQL (with `pgvector`), Ollama, and the app, then pulls the
`nomic-embed-text` embedding model into Ollama — one command, nothing to set up by hand.

```bash
make help   # every available command
```

### Local development without Docker

```bash
make sync    # install dependencies
make check   # lint + typecheck + test, mirrors CI exactly
```

## 📌 Status

Pre-v0.1. The scope was cut to one vertical slice that runs end to end, and it is being
implemented now — the sections above describe that slice, not a shipped release. `make up`
does not yet complete a full ingest cycle.

What already works: `LLMClient` (forced structured output, cost tracking, prompt caching) and
the database schema. Everything else in the pipeline is being written. The previous full
scaffold — 43 modules, most of them unimplemented — is preserved under the tag
`v0.0-scaffold`.

See [AGENTS.md](./AGENTS.md) for the module map, the engineering rules, and the explicit list
of what is deliberately out of scope.

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](./CONTRIBUTING.md) first.

## 📄 License

MIT © [Dawid Bińkowski](https://github.com/binkowskidawid)

See [LICENSE](./LICENSE) for details.
