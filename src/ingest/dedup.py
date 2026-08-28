"""Deduplication.

Two levels, and the important one is not in Python:

  `UNIQUE (source, external_id)` in the schema decides what is new. The database, not this
  module — an application-level "select then insert" races itself the moment two cycles
  overlap, and the second one silently sends the same offer twice.

  `identity_key` catches the same job posted under two ids or on two boards. It is a hint for
  later stages, not a constraint: identical titles at one company are common enough
  (two openings, two locations) that rejecting on it would lose real offers.
"""

import hashlib
import logging
import re
import unicodedata

from psycopg import AsyncConnection
from psycopg.rows import DictRow

from domain.offer import Offer

logger = logging.getLogger(__name__)

_NOISE = re.compile(r"\(.*?\)|\[.*?\]")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")

# Seniority and contract noise that differs between boards for the same posting.
_STOP = {
    "senior", "mid", "junior", "regular", "lead", "principal", "staff",
    "developer", "engineer", "specialist", "programista", "inzynier",
    "remote", "zdalnie", "hybrid", "b2b", "uop", "fulltime", "full", "time",
    "m", "f", "d", "k", "x",
}  # fmt: skip


def identity_key(offer: Offer) -> str:
    """A stable fingerprint of "which job this is", independent of the board it came from."""
    title = _normalise(offer.title)
    company = _normalise(offer.company or "")
    return hashlib.sha256(f"{company}|{title}".encode()).hexdigest()


def _normalise(text: str) -> str:
    # Strip accents so "Kraków" and "Krakow" agree, then drop the words boards disagree about.
    folded = unicodedata.normalize("NFKD", text.lower())
    ascii_only = "".join(c for c in folded if not unicodedata.combining(c))
    words = _WS.sub(" ", _NON_WORD.sub(" ", _NOISE.sub(" ", ascii_only))).split()
    return " ".join(sorted(w for w in words if w not in _STOP and len(w) > 1))


async def save(conn: AsyncConnection[DictRow], offer: Offer) -> bool:
    """Insert the offer, returning True when it is new and therefore worth scoring.

    A repeat sighting bumps `last_seen_at` and `times_seen` instead: an offer that keeps
    reappearing is evidence about the posting, not a reason to notify again.
    """
    row = await (
        await conn.execute(
            """
            INSERT INTO offer (source, external_id, identity_key, url, payload)
            VALUES (%(source)s, %(external_id)s, %(identity_key)s, %(url)s, %(payload)s)
            ON CONFLICT (source, external_id) DO UPDATE
                SET last_seen_at = now(),
                    times_seen   = offer.times_seen + 1
            RETURNING id, (xmax = 0) AS inserted
            """,
            {
                "source": offer.source,
                "external_id": offer.external_id,
                "identity_key": identity_key(offer),
                "url": str(offer.url),
                "payload": offer.model_dump_json(),
            },
        )
    ).fetchone()

    if row is None:  # pragma: no cover — RETURNING always yields a row here
        return False
    is_new = bool(row["inserted"])
    logger.debug("%s/%s: %s", offer.source, offer.external_id, "new" if is_new else "seen")
    return is_new


async def known_external_ids(conn: AsyncConnection[DictRow], source: str) -> set[str]:
    """Every `external_id` already stored for a source, in one query.

    Adapters use this to skip fetching pages for offers already on disk. One round trip for
    the whole set, never one per offer — the rule against queries inside loops applies to the
    network too.
    """
    rows = await (
        await conn.execute("SELECT external_id FROM offer WHERE source = %s", (source,))
    ).fetchall()
    return {row["external_id"] for row in rows}
