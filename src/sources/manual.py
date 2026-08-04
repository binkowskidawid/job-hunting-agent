"""Manual-paste adapter — always legal, zero maintenance. Build and use this one first
to unblock everything else before the real source adapters are ready."""

from domain.offer import Offer
from sources.base import Adapter


class Manual(Adapter):
    name = "manual"
    basis = "manual"

    async def fetch(self) -> list[Offer]:
        raise NotImplementedError
