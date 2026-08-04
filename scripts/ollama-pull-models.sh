#!/usr/bin/env bash
# Pulls the embedding model into the running Ollama container. Idempotent — `ollama pull`
# skips models already present, so this is safe to run on every `make up`.
set -euo pipefail

EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
COMPOSE="${COMPOSE:-docker compose}"

echo "-> Waiting for Ollama to accept connections..."
for _ in $(seq 1 30); do
  if $COMPOSE exec -T ollama ollama list >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! $COMPOSE exec -T ollama ollama list >/dev/null 2>&1; then
  echo "Ollama did not become ready in time." >&2
  exit 1
fi

echo "-> ollama pull $EMBED_MODEL"
$COMPOSE exec -T ollama ollama pull "$EMBED_MODEL"

echo "-> Models available:"
$COMPOSE exec -T ollama ollama list
