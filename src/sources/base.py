"""Adapter base class — one subclass per data source, each declaring its legal/ethical
basis for access.

Network hygiene lives here rather than in each adapter so it cannot be skipped: an honest
User-Agent, a timeout on every request, bounded retries, and `Retry-After` respected when the
server asks for a pause. A source that blocks this project blocks it for everyone using it.
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod

import httpx

from domain.offer import Offer

logger = logging.getLogger(__name__)

CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "you@example.com")
# Says who is asking and gives the operator someone to email instead of a reason to block.
USER_AGENT = f"JobAgent/1.0 (private single-user tool; contact: {CONTACT_EMAIL})"

TIMEOUT_S = 30.0
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 2.0


class Adapter(ABC):
    name: str
    # How this project is entitled to the data. Recorded per adapter and audited in
    # SOURCES.md, because "it was reachable" is not a basis.
    basis: str  # 'official_api' | 'rss_feed' | 'sitemap_jsonld' | 'email_alert' | 'manual'
    min_interval_s: int = 300

    @abstractmethod
    async def fetch(self) -> list[Offer]:
        raise NotImplementedError


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_S,
        follow_redirects=True,
    )


async def fetch_text(http: httpx.AsyncClient, url: str) -> str | None:
    """GET `url`, returning None rather than raising when the source is simply unavailable.

    A dead source must not take down the ingest cycle: the other adapters still have work to
    do, and the failure is a monitoring signal, not a crash.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await http.get(url)
        except httpx.HTTPError as exc:
            logger.warning("%s: request failed (%s/%s): %s", url, attempt, MAX_ATTEMPTS, exc)
        else:
            if response.status_code == httpx.codes.OK:
                return response.text
            if response.status_code < httpx.codes.INTERNAL_SERVER_ERROR and (
                response.status_code != httpx.codes.TOO_MANY_REQUESTS
            ):
                # 404 or 403 will not become a 200 by asking again.
                logger.warning("%s: HTTP %s, not retrying", url, response.status_code)
                return None
            logger.warning("%s: HTTP %s (%s/%s)", url, response.status_code, attempt, MAX_ATTEMPTS)
            retry_after = _retry_after(response)
            if retry_after is not None:
                await asyncio.sleep(retry_after)
                continue

        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(BACKOFF_BASE_S**attempt)
    return None


def _retry_after(response: httpx.Response) -> float | None:
    """Honour an explicit `Retry-After`; ignore the HTTP-date form, which is rare here."""
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None
