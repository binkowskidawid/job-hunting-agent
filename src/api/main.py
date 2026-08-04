"""FastAPI app exposing the recruiter-message draft/review/decide endpoints, backed by a
LangGraph Postgres checkpointer. Only started via the `extension` Docker Compose profile."""

from fastapi import FastAPI

app = FastAPI()
