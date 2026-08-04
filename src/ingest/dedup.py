"""Three-level deduplication: (source, external_id) -> normalized-title hash ->
(future) embedding similarity. Enforced by a UNIQUE constraint in the database, not
by application logic alone."""

from domain.offer import Offer


def identity_key(offer: Offer) -> str:
    raise NotImplementedError


async def save(conn: object, offer: Offer) -> bool:
    """Returns True if the offer is new (worth scoring and notifying about)."""
    raise NotImplementedError
