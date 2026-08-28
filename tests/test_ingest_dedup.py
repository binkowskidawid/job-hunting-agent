"""Deduplication.

`save` runs against a real Postgres because what it tests — `UNIQUE (source, external_id)`
and the `xmax = 0` inserted/updated signal — is database behaviour. A mock would assert that
the mock works.
"""

import psycopg
import pytest
from psycopg.rows import DictRow

from domain.offer import Offer
from ingest.dedup import identity_key, known_external_ids, save


def _offer(**overrides: object) -> Offer:
    base = {
        "source": "test",
        "external_id": "abc-123",
        "url": "https://example.test/job/abc-123",
        "title": "Senior Python Developer",
        "company": "Acme",
    }
    return Offer.model_validate(base | overrides)


def test_identity_key_ignores_seniority_and_role_noise() -> None:
    # The same posting listed as "Senior Python Developer" on one board and
    # "Python Developer (Senior)" on another is one job.
    assert identity_key(_offer(title="Senior Python Developer")) == identity_key(
        _offer(title="Python Developer (Senior)")
    )


def test_identity_key_ignores_accents_and_case() -> None:
    assert identity_key(_offer(company="Żabka")) == identity_key(_offer(company="zabka"))


def test_identity_key_separates_different_jobs_at_one_company() -> None:
    assert identity_key(_offer(title="Python Developer")) != identity_key(
        _offer(title="Frontend Developer")
    )


def test_identity_key_separates_the_same_title_at_different_companies() -> None:
    assert identity_key(_offer(company="Acme")) != identity_key(_offer(company="Globex"))


async def test_save_reports_a_first_sighting_as_new(
    conn: psycopg.AsyncConnection[DictRow], offer: Offer
) -> None:
    assert await save(conn, offer) is True


async def test_save_reports_a_repeat_as_seen_and_counts_it(
    conn: psycopg.AsyncConnection[DictRow], offer: Offer
) -> None:
    await save(conn, offer)

    assert await save(conn, offer) is False

    row = await (
        await conn.execute(
            "SELECT times_seen FROM offer WHERE source = %s AND external_id = %s",
            (offer.source, offer.external_id),
        )
    ).fetchone()
    assert row is not None
    assert row["times_seen"] == 2


async def test_the_same_id_from_another_source_is_a_different_offer(
    conn: psycopg.AsyncConnection[DictRow], offer: Offer
) -> None:
    await save(conn, offer)

    assert await save(conn, offer.model_copy(update={"source": "other"})) is True


async def test_known_external_ids_returns_one_source_in_one_query(
    conn: psycopg.AsyncConnection[DictRow], offer: Offer
) -> None:
    await save(conn, offer)
    await save(conn, offer.model_copy(update={"external_id": "def-456"}))
    await save(conn, offer.model_copy(update={"source": "other", "external_id": "zzz"}))

    assert await known_external_ids(conn, "test") == {"abc-123", "def-456"}


@pytest.mark.parametrize("missing", ["company"])
async def test_save_accepts_an_offer_with_fields_the_source_did_not_provide(
    conn: psycopg.AsyncConnection[DictRow], offer: Offer, missing: str
) -> None:
    # Roughly a third of real postings omit a salary range, and plenty omit the company.
    assert await save(conn, offer.model_copy(update={missing: None})) is True
