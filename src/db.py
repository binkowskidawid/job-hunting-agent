"""The only path to Postgres: one connection pool for the lifetime of the process.

Every caller takes a connection from here. Opening a fresh connection per query costs a TCP
handshake plus a TLS negotiation plus Postgres forking a backend, which is several times the
cost of the queries this project runs.
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

# One ingest cycle and the Discord bot's button callbacks are the only concurrent users, and
# a single-user tool never has more of either. A larger pool would idle.
MIN_SIZE = 1
MAX_SIZE = 4

_pool: AsyncConnectionPool[AsyncConnection[DictRow]] | None = None


async def open_pool(dsn: str | None = None) -> None:
    """Open the process-wide pool. Call once at startup."""
    global _pool
    if _pool is not None:
        raise RuntimeError("The pool is already open; call close_pool() before reopening.")

    conninfo = dsn or os.environ.get("DATABASE_URL")
    if not conninfo:
        raise RuntimeError("DATABASE_URL is not set — copy .env.example to .env and fill it in.")

    _pool = AsyncConnectionPool(
        conninfo=conninfo,
        min_size=MIN_SIZE,
        max_size=MAX_SIZE,
        # Rows come back as dicts so callers read columns by name; a positional tuple silently
        # keeps working when a SELECT's column order changes, and starts returning the wrong
        # field.
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await _pool.open(wait=True)
    logger.info("Postgres pool open (min=%d, max=%d)", MIN_SIZE, MAX_SIZE)


async def close_pool() -> None:
    """Close the pool. Safe to call when it was never opened."""
    global _pool
    if _pool is None:
        return
    await _pool.close()
    _pool = None
    logger.info("Postgres pool closed")


@asynccontextmanager
async def connection() -> AsyncIterator[AsyncConnection[DictRow]]:
    """Borrow a connection for the duration of the block.

    The transaction commits on a clean exit and rolls back on an exception, so a partially
    scored offer never lands in the database.
    """
    if _pool is None:
        raise RuntimeError("The pool is not open — call open_pool() during startup.")
    async with _pool.connection() as conn:
        yield conn
