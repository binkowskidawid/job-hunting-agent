"""Sitemap for discovery, schema.org JSON-LD for content.

Named after the mechanism, not after a board: both halves are open standards, so one adapter
serves every site that publishes them. Which sites those are is `sources.yaml`'s business.

  Discovery   sitemaps.org XML, which `robots.txt` normally advertises with a `Sitemap:`
              directive — an explicit invitation. One request returns every active posting.
  Content     a schema.org `JobPosting` block in `application/ld+json` on the offer page, the
              format boards emit for Google for Jobs and other aggregators.

Per-site facts — the sitemap URL, the crawl budget, and the `robots.txt` reading that justifies
using it at all — live in `sources.yaml` and `SOURCES.md`, never here. justjoin.it, the first
site configured, also exposes a JSON API, and its `robots.txt` says `Disallow: /api/`; this
adapter reaches for neither, because it only knows about sitemaps and offer pages.

Fetching every posting a sitemap lists would be thousands of requests a day for a handful of
relevant ones, so the caller injects `should_fetch`: the cost cascade this project is built
around, applied one layer earlier — on the network rather than on the model.
"""

import asyncio
import json
import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import httpx
from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring
from pydantic import HttpUrl, ValidationError

from domain.offer import ContractType, Offer, WorkMode
from sources.base import Adapter, client, fetch_text

logger = logging.getLogger(__name__)

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"

_LD_BLOCK = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

# schema.org QuantitativeValue.unitText -> the `period` this project records.
_PERIOD = {"HOUR": "hour", "DAY": "day", "WEEK": "week", "MONTH": "month", "YEAR": "year"}

# A courtesy pause between offer pages. The sitemap costs one request; the pages are the part
# that could look like a crawl if fired off all at once.
DEFAULT_DELAY_S = 1.0
DEFAULT_MAX_FETCHES = 200


class SitemapJsonLdAdapter(Adapter):
    basis = "sitemap_jsonld"

    def __init__(
        self,
        name: str,
        sitemap_url: str,
        *,
        should_fetch: Callable[[str], bool] | None = None,
        max_fetches: int = DEFAULT_MAX_FETCHES,
        delay_s: float = DEFAULT_DELAY_S,
        min_interval_s: int = 86_400,
    ) -> None:
        self.name = name
        self.min_interval_s = min_interval_s
        self.sitemap_url = sitemap_url
        self.should_fetch = should_fetch or (lambda _url: True)
        self.max_fetches = max_fetches
        self.delay_s = delay_s

    async def fetch(self) -> list[Offer]:
        async with client() as http:
            urls = await self._discover(http)
            wanted = [u for u in urls if self.should_fetch(u)]
            logger.info(
                "%s: %d in sitemap, %d wanted, fetching at most %d",
                self.name,
                len(urls),
                len(wanted),
                self.max_fetches,
            )
            if len(wanted) > self.max_fetches:
                logger.warning(
                    "%s: %d wanted exceeds the per-cycle cap; the rest wait for the next run",
                    self.name,
                    len(wanted),
                )

            offers = []
            for index, url in enumerate(wanted[: self.max_fetches]):
                if index:
                    await asyncio.sleep(self.delay_s)
                page = await fetch_text(http, url)
                if page is None:
                    continue
                offer = self.parse_offer(page, url)
                if offer is not None:
                    offers.append(offer)
        logger.info("%s: %d offers parsed", self.name, len(offers))
        return offers

    async def _discover(self, http: httpx.AsyncClient) -> list[str]:
        """Resolve the sitemap, following one level of `sitemapindex` if present."""
        body = await fetch_text(http, self.sitemap_url)
        if body is None:
            return []
        root = _parse_xml(body, self.sitemap_url)
        if root is None:
            return []

        if root.tag == f"{SITEMAP_NS}sitemapindex":
            urls = []
            for part in _locs(root, "sitemap"):
                part_body = await fetch_text(http, part)
                part_root = _parse_xml(part_body, part) if part_body else None
                if part_root is not None:
                    urls.extend(_locs(part_root, "url"))
            return urls
        return _locs(root, "url")

    def parse_offer(self, page: str, url: str) -> Offer | None:
        posting = _job_posting(page)
        if posting is None:
            logger.warning("%s: no JobPosting block at %s", self.name, url)
            return None

        salary_min, salary_max, currency, period = _salary(posting.get("baseSalary"))
        try:
            return Offer(
                source=self.name,
                external_id=url.rstrip("/").rsplit("/", 1)[-1],
                url=HttpUrl(url),
                title=str(posting.get("title", "")).strip(),
                company=_company(posting),
                description=_plain(str(posting.get("description", ""))),
                salary_min=salary_min,
                salary_max=salary_max,
                currency=currency or "PLN",
                period=period,
                # schema.org `employmentType` says FULL_TIME/PART_TIME, which is orthogonal to
                # the B2B-versus-employment distinction the filters care about. Left unknown
                # rather than guessed.
                contract_type=ContractType.UNKNOWN,
                work_mode=_work_mode(posting),
                locations=_locations(posting),
                # No technologies here. The obvious source is the trailing slug segment, but
                # measured across justjoin.it's 9,955 live postings that segment takes 2,680
                # distinct values including `pm`, `data`, `analytics`, `other` and hash
                # suffixes — a board's own taxonomy, not a tech stack. The cascade reads
                # technologies out of the title and description instead.
                published_at=_published(posting),
            )
        except ValidationError as exc:
            logger.warning("%s: skipping %s: %s", self.name, url, exc)
            return None


def _parse_xml(body: str, source: str) -> ET.Element | None:
    try:
        root: ET.Element = fromstring(body)
    except (ET.ParseError, DefusedXmlException) as exc:
        logger.warning("%s: XML rejected: %s", source, exc)
        return None
    return root


def _locs(root: ET.Element, child: str) -> list[str]:
    return [
        loc.text.strip()
        for element in root.findall(f"{SITEMAP_NS}{child}")
        if (loc := element.find(f"{SITEMAP_NS}loc")) is not None and loc.text
    ]


def _job_posting(page: str) -> dict[str, Any] | None:
    for block in _LD_BLOCK.findall(page):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for candidate in data if isinstance(data, list) else [data]:
            if isinstance(candidate, dict) and candidate.get("@type") == "JobPosting":
                return candidate
    return None


def _plain(html_text: str) -> str:
    from html import unescape

    return _WS.sub(" ", unescape(_TAG.sub(" ", html_text))).strip()


def _company(posting: dict[str, Any]) -> str | None:
    org = posting.get("hiringOrganization")
    if isinstance(org, dict) and (name := org.get("name")):
        return str(name).strip()
    return None


def _salary(
    base: object,
) -> tuple[int | None, int | None, str | None, str | None]:
    if not isinstance(base, dict):
        return None, None, None, None
    value = base.get("value")
    if not isinstance(value, dict):
        return None, None, None, None
    low = value.get("minValue", value.get("value"))
    high = value.get("maxValue", value.get("value"))
    period = _PERIOD.get(str(value.get("unitText", "")).upper())
    currency = str(base.get("currency", "")).upper() or None
    return _int(low), _int(high), currency, period


def _int(raw: object) -> int | None:
    try:
        return int(float(raw))  # type: ignore[arg-type]  # any non-numeric raises below
    except TypeError, ValueError:
        return None


def _work_mode(posting: dict[str, Any]) -> WorkMode:
    if str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        return WorkMode.REMOTE
    return WorkMode.ONSITE if posting.get("jobLocation") else WorkMode.UNKNOWN


def _locations(posting: dict[str, Any]) -> list[str]:
    places = posting.get("jobLocation")
    found = []
    for place in places if isinstance(places, list) else [places]:
        if not isinstance(place, dict):
            continue
        address = place.get("address")
        if isinstance(address, dict) and (city := address.get("addressLocality")):
            found.append(str(city).strip())
    return found


def _published(posting: dict[str, Any]) -> date | None:
    raw = str(posting.get("datePosted", "")).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        logger.debug("unparseable datePosted: %r", raw)
        return None
