"""Rule-based filter — the free, deterministic first stage of the scoring cascade.
Every rejection must carry a reason."""

from dataclasses import dataclass
from typing import Any

from domain.offer import Offer


@dataclass
class FilterResult:
    passed: bool
    reason: str | None
    features: dict[str, Any]


def filter_offer(offer: Offer, cfg: dict[str, Any]) -> FilterResult:
    raise NotImplementedError


def _salary_threshold(offer: Offer, cfg: dict[str, Any]) -> int | None:
    raise NotImplementedError
