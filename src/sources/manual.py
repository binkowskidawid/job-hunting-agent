"""Manual-paste adapter — always legal, zero maintenance.

Reads a JSONL file of `Offer` objects. It is what feeds the reference set under `eval/`, and
the fallback for any board with no feed, no sitemap and no structured data.
"""

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from domain.offer import Offer
from sources.base import Adapter

logger = logging.getLogger(__name__)


class Manual(Adapter):
    basis = "manual"
    min_interval_s = 0

    def __init__(self, name: str, path: Path) -> None:
        self.name = name
        self.path = path

    async def fetch(self) -> list[Offer]:
        if not self.path.exists():
            logger.info("%s: %s does not exist yet", self.name, self.path)
            return []

        offers = []
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                offers.append(Offer.model_validate(json.loads(line)))
            except (json.JSONDecodeError, ValidationError) as exc:
                # Name the line: a hand-maintained file is edited by hand, and "invalid JSON"
                # without a line number is a hunt.
                logger.warning("%s: %s line %d rejected: %s", self.name, self.path, number, exc)
        logger.info("%s: %d offers from %s", self.name, len(offers), self.path)
        return offers
