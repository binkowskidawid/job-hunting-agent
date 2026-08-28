# Security Policy

## Supported Versions

This project is in active development. Security patches apply to the latest commit on `main`
only — there are no numbered releases yet.

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not open a public GitHub issue**.

Instead, report it privately via GitHub's private vulnerability reporting
(Security tab -> "Report a vulnerability").

Please include: a clear description and potential impact, the affected component(s), and
steps to reproduce.

### Response Timeline

| Stage | Target time |
| --- | --- |
| Initial acknowledgement | Within 48h |
| Triage & severity assessment | Within 5 days |
| Patch or mitigation released | Within 30 days (critical: 7 days) |

## Scope

In scope:

- Prompt injection paths where untrusted content (job posting text, CV content) could reach
  the LLM's system prompt or influence tool permissions
- Exposed secrets, API keys, or `.env` values
- SQL injection in raw queries against Postgres
- Insecure deserialization of LLM or tool output before validation

Out of scope:

- Vulnerabilities in third-party dependencies already publicly disclosed (open a regular PR
  bumping the dependency instead)
- Findings from automated scanners without a verified proof-of-concept

## Security Considerations for Self-Hosters

This project is designed to be self-hosted, for a single user, via Docker Compose.

### Secrets

- Never commit `.env` — only `.env.example` (with empty/placeholder values) is tracked
- `ANTHROPIC_API_KEY` and `DISCORD_BOT_TOKEN` should be treated as production secrets even in
  a personal deployment

### Network Exposure

- `docker-compose.yml` binds Postgres (`5432`) and Ollama (`11434`) to `127.0.0.1` only —
  never change this to `0.0.0.0` or a public interface
- If you enable the optional `api` (recruiter-message-drafting extension) beyond `localhost`,
  put it behind authentication and a reverse proxy — it is not authenticated by default

### Data Sourcing

- This project's design explicitly avoids collecting recruiters' personal data and avoids
  redistributing job-posting content — see the source-adapter guidelines in `AGENTS.md`
- Adapters that hit real job-board APIs must declare a `basis` (`official_api` / `rss_feed` /
  `email_alert` / `manual`) — undocumented scraping is out of scope for what this project
  should be extended to do

## Dependency Security

Enable Dependabot on the repository. Audit the dependency tree at any time:

```bash
uv tree
```
