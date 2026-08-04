"""Combines filter features + similarity + kNN into one score, then decides:
send / reject / ask the LLM judge."""

from typing import Any


def combine_score(
    features: dict[str, Any],
    similarity: dict[str, Any],
    knn: dict[str, Any] | None,
    weights: dict[str, Any],
) -> float:
    raise NotImplementedError


def decide(score: float, thresholds: dict[str, Any], features: dict[str, Any]) -> str:
    """Returns 'send' | 'reject' | 'ask_llm'."""
    raise NotImplementedError
