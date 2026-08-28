"""Build adapters from `sources.yaml`.

Adding a board is a config entry, not a module: `type` selects a mechanism adapter and the
rest of the entry is that adapter's arguments. The mechanisms are open standards, so one
implementation covers every site that speaks them.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from sources.base import Adapter
from sources.manual import Manual
from sources.rss import RssAdapter
from sources.sitemap_jsonld import SitemapJsonLdAdapter

logger = logging.getLogger(__name__)

SOURCES_PATH = Path(__file__).parent / "sources.yaml"


class SourceEntry(BaseModel):
    name: str
    type: Literal["rss", "sitemap_jsonld", "manual"]
    enabled: bool = True
    # Why this project is entitled to the data. Required, and audited in SOURCES.md.
    basis_note: str = Field(min_length=1)
    min_interval_s: int = 900

    url: str | None = None  # rss
    sitemap: str | None = None  # sitemap_jsonld
    path: str | None = None  # manual
    max_fetches: int = 200
    delay_s: float = 1.0


class Sources(BaseModel):
    sources: list[SourceEntry] = []


def load_sources(path: Path = SOURCES_PATH) -> Sources:
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing.")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        return Sources.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{path.name} is invalid:\n{exc}") from exc


def build_adapters(
    sources: Sources,
    *,
    should_fetch: Callable[[str], bool] | None = None,
) -> list[Adapter]:
    """Instantiate every enabled source. `should_fetch` gates page fetches for crawling
    adapters; the caller composes it from "not already in the database" and the cheap rules."""
    adapters: list[Adapter] = []
    for entry in sources.sources:
        if not entry.enabled:
            continue
        adapter = _build(entry, should_fetch)
        if adapter is None:
            logger.warning("%s: incomplete configuration for type %r", entry.name, entry.type)
            continue
        adapters.append(adapter)
    return adapters


def _build(entry: SourceEntry, should_fetch: Callable[[str], bool] | None) -> Adapter | None:
    match entry.type:
        case "rss" if entry.url:
            return RssAdapter(entry.name, entry.url, min_interval_s=entry.min_interval_s)
        case "sitemap_jsonld" if entry.sitemap:
            return SitemapJsonLdAdapter(
                entry.name,
                entry.sitemap,
                should_fetch=should_fetch,
                max_fetches=entry.max_fetches,
                delay_s=entry.delay_s,
                min_interval_s=entry.min_interval_s,
            )
        case "manual" if entry.path:
            return Manual(entry.name, Path(entry.path))
        case _:
            return None
