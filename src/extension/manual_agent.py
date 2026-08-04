"""Hand-written tool-calling agent loop — the ~60 lines that make agents stop being
magic. Migrated to LangGraph once state and human-in-the-loop are needed."""

from typing import Any

MAX_ITERATIONS = 8
MAX_COST_USD = 0.50


def run_tool(name: str, args: dict[str, Any], dsn: str) -> str:
    raise NotImplementedError


def draft_recruiter_message(
    system: str, user_input: str, dsn: str, model: str = "claude-sonnet-5"
) -> dict[str, Any]:
    raise NotImplementedError
