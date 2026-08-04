"""Glues the four stages together — the cost-aware pipeline this whole project is
built around."""

from typing import Any

from domain.offer import Offer
from llm_client import LLMClient

VERSION = "cascade.v1"


async def score(
    conn: object, llm: LLMClient, offer: Offer, profile: dict[str, Any], cfg: dict[str, Any]
) -> dict[str, Any]:
    raise NotImplementedError
