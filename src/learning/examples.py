"""Few-shot example selection for the LLM judge: nearest positive, nearest negative,
and — most informative — the borderline cases."""

from typing import Any


async def pick_examples(conn: object, offer_vector: object, n: int = 6) -> list[dict[str, Any]]:
    raise NotImplementedError
