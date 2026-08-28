"""Pool lifecycle guards.

These cover the paths that must fail loudly without reaching Postgres. Pooling against a real
database is exercised by the ingest tests, which need one anyway.
"""

import pytest

import db


async def test_connection_before_open_says_what_to_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "_pool", None)

    with pytest.raises(RuntimeError, match="open_pool"):
        async with db.connection():
            pass


async def test_open_without_a_dsn_points_at_the_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        await db.open_pool()


async def test_reopening_an_open_pool_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # A second open would leak the first pool's connections silently.
    monkeypatch.setattr(db, "_pool", object())

    with pytest.raises(RuntimeError, match="already open"):
        await db.open_pool("postgresql://unused")


async def test_closing_a_pool_that_was_never_opened_is_a_no_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db, "_pool", None)

    await db.close_pool()
