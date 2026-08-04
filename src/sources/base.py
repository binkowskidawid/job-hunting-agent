"""Adapter base class — one subclass per data source, each declaring its legal/ethical
basis for access."""

from abc import ABC, abstractmethod

from domain.offer import Offer


class Adapter(ABC):
    name: str
    basis: str  # 'official_api' | 'rss_feed' | 'email_alert' | 'manual'
    min_interval_s: int = 300

    @abstractmethod
    async def fetch(self) -> list[Offer]:
        raise NotImplementedError
