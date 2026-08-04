"""Deliberately sends a few below-threshold offers so the system doesn't trap itself
in a feedback-loop filter bubble."""

from typing import Any

EXPLORATION_BUDGET = 0.15


async def pick_for_exploration(
    conn: object, candidates: list[dict[str, Any]], count: int = 1
) -> list[dict[str, Any]]:
    raise NotImplementedError
