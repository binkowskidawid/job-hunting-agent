"""Shared fixtures.

The database fixture skips rather than fails when no Postgres is reachable, so `make check`
works on a laptop with nothing running. CI always provides one, so the integration tests are
never quietly skipped where it matters.
"""

import os
from collections.abc import AsyncIterator

import psycopg
import pytest
from psycopg.rows import DictRow, dict_row
from pydantic import HttpUrl

from domain.offer import Offer

TEST_DSN_ENV = ("TEST_DATABASE_URL", "DATABASE_URL")


def _dsn() -> str | None:
    for name in TEST_DSN_ENV:
        if value := os.environ.get(name):
            return value
    return None


@pytest.fixture
async def conn() -> AsyncIterator[psycopg.AsyncConnection[DictRow]]:
    """A connection whose work is rolled back, so tests cannot see each other's rows."""
    dsn = _dsn()
    if not dsn:
        pytest.skip("no TEST_DATABASE_URL/DATABASE_URL; start Postgres with `make up`")
    try:
        connection = await psycopg.AsyncConnection.connect(dsn, row_factory=dict_row)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres unreachable: {exc}")

    async with connection:
        yield connection
        await connection.rollback()


@pytest.fixture
def offer() -> Offer:
    return Offer(
        source="test",
        external_id="abc-123",
        url=HttpUrl("https://example.test/job/abc-123"),
        title="Senior Python Developer",
        company="Acme",
        description="Backend work.",
        salary_min=20000,
        salary_max=26000,
        period="month",
    )
