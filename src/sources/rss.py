"""Generic RSS 2.0 / Atom adapter.

`basis = "rss_feed"`: a feed is published for machines to read, so consuming one needs no
further justification than fetching it politely.

Deliberately generic — the feed URL comes from `sources.yaml`, never from code, so adding a
board that publishes a feed is a config change. What a feed actually carries varies wildly:
title and link are guaranteed, everything else is best-effort. Fields this parser cannot find
stay `None` and the cascade treats them as unknown rather than as zero.
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html import unescape

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring
from pydantic import HttpUrl, ValidationError

from domain.offer import ContractType, Offer, WorkMode
from sources.base import Adapter, client, fetch_text

logger = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

# "Senior Python Developer @ Acme" — the convention used by the Polish boards. A feed that
# does not follow it simply yields no company, which is a missing field, not a wrong one.
_TITLE_COMPANY = re.compile(r"^(?P<title>.+?)\s+@\s+(?P<company>.+)$")

# Labelled fields inside a description: "<b>Salary:</b> from 50 to 60 PLN per hour".
_LABELLED = re.compile(r"<b>\s*([^<:]+?)\s*:?\s*</b>\s*(.*?)(?=<b>|</p>|$)", re.S | re.I)

# Two salary spellings seen in the wild: the worded range these feeds use, and the dash range
# used almost everywhere else. Matching only the dash form finds nothing on a worded feed —
# and silently, because every offer then looks like it has no range at all.
_WORDED = re.compile(r"from\s+([\d\s]+?)\s+to\s+([\d\s]+?)\s+([A-Z]{3})\s+per\s+(\w+)", re.I)
# The class holds hyphen-minus plus U+2013 and U+2014, written as escapes: job postings
# genuinely use all three for ranges, and a literal one here reads as a typo at a glance.
_DASHED = re.compile(
    "([\\d\\s]{3,}?)\\s*[-\u2013\u2014]\\s*([\\d\\s]{3,}?)\\s*(PLN|EUR|USD|GBP)", re.I
)
_SINGLE = re.compile(r"([\d\s]{3,}?)\s+([A-Z]{3})\s+per\s+(\w+)", re.I)

_REMOTE = re.compile(r"\bremote\b|\bzdaln", re.I)
_HYBRID = re.compile(r"\bhybrid\b|\bhybryd", re.I)


class RssAdapter(Adapter):
    basis = "rss_feed"

    def __init__(self, name: str, url: str, min_interval_s: int = 900) -> None:
        self.name = name
        self.url = url
        self.min_interval_s = min_interval_s

    async def fetch(self) -> list[Offer]:
        async with client() as http:
            body = await fetch_text(http, self.url)
        if body is None:
            return []
        return self.parse(body)

    def parse(self, body: str) -> list[Offer]:
        # defusedxml, not the stdlib parser: a feed is remote input. Measured on Python 3.14,
        # xml.etree resolves no external entities (XXE is already dead) but expands internal
        # ones — a 700-byte "billion laughs" document became 30,000 characters, and one more
        # nesting level is gigabytes. defusedxml refuses entity declarations outright.
        try:
            root: ET.Element = fromstring(body)
        except (ET.ParseError, DefusedXmlException) as exc:
            logger.warning("%s: feed rejected: %s", self.name, exc)
            return []

        entries = root.findall(".//item") or root.findall(f".//{ATOM}entry")
        offers = []
        for entry in entries:
            offer = self._to_offer(entry)
            if offer is not None:
                offers.append(offer)
        logger.info("%s: %d entries, %d parsed", self.name, len(entries), len(offers))
        return offers

    def _to_offer(self, entry: ET.Element) -> Offer | None:
        link = _text(entry, "link") or _atom_link(entry)
        raw_title = _text(entry, "title") or _text(entry, f"{ATOM}title")
        if not link or not raw_title:
            return None

        title, company = _split_title(raw_title)
        description_html = (
            _text(entry, "description")
            or _text(entry, f"{ATOM}summary")
            or _text(entry, f"{ATOM}content")
            or ""
        )
        fields = {k.lower(): _plain(v) for k, v in _LABELLED.findall(description_html)}
        salary = _parse_salary(fields.get("salary", ""))
        location = fields.get("location", "")

        try:
            return Offer(
                source=self.name,
                external_id=_text(entry, "guid") or _text(entry, f"{ATOM}id") or link,
                url=HttpUrl(link),
                title=title,
                company=company,
                description=_plain(description_html),
                salary_min=salary[0],
                salary_max=salary[1],
                currency=salary[2] or "PLN",
                period=salary[3],
                contract_type=ContractType.UNKNOWN,
                work_mode=_work_mode(f"{raw_title} {location} {description_html}"),
                locations=[location] if location else [],
                published_at=_published(entry),
            )
        except ValidationError as exc:
            # One malformed entry is not a reason to drop the other four thousand.
            logger.warning("%s: skipping %r: %s", self.name, link, exc)
            return None


def _text(entry: ET.Element, tag: str) -> str:
    """Read a child's text, unescaping once more than the XML parser already did.

    Real feeds double-escape: NoFluffJobs ships `&amp;amp;`, which the XML parser resolves to
    `&amp;`, and without this second pass that string reaches the embedding and the Discord
    card verbatim.
    """
    found = entry.findtext(tag)
    return unescape(found).strip() if found else ""


def _atom_link(entry: ET.Element) -> str:
    for link in entry.findall(f"{ATOM}link"):
        href = link.get("href")
        if href and link.get("rel", "alternate") == "alternate":
            return href
    return ""


def _plain(html_text: str) -> str:
    return _WS.sub(" ", unescape(_TAG.sub(" ", html_text))).strip()


def _split_title(raw: str) -> tuple[str, str | None]:
    match = _TITLE_COMPANY.match(raw)
    if match:
        return match["title"].strip(), match["company"].strip()
    return raw, None


def _digits(raw: str) -> int:
    return int(re.sub(r"\D", "", raw))


def _parse_salary(text: str) -> tuple[int | None, int | None, str | None, str | None]:
    if not text:
        return None, None, None, None
    if m := _WORDED.search(text):
        return _digits(m[1]), _digits(m[2]), m[3].upper(), m[4].lower()
    if m := _DASHED.search(text):
        return _digits(m[1]), _digits(m[2]), m[3].upper(), None
    if m := _SINGLE.search(text):
        value = _digits(m[1])
        return value, value, m[2].upper(), m[3].lower()
    return None, None, None, None


def _work_mode(text: str) -> WorkMode:
    if _REMOTE.search(text):
        return WorkMode.REMOTE
    if _HYBRID.search(text):
        return WorkMode.HYBRID
    return WorkMode.UNKNOWN


def _published(entry: ET.Element) -> date | None:
    raw = (
        _text(entry, "pubDate")
        or _text(entry, f"{ATOM}published")
        or _text(entry, f"{ATOM}updated")
    )
    if not raw:
        return None
    for parse in (parsedate_to_datetime, datetime.fromisoformat):
        try:
            return parse(raw).date()
        except TypeError, ValueError:
            continue
    logger.debug("unparseable date: %r", raw)
    return None
