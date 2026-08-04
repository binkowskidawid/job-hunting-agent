"""Cron-driven ingest cycle: idempotent, crash-tolerant, respects the exploration
budget."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler


def register(sched: AsyncIOScheduler, ctx: object) -> None:
    raise NotImplementedError


async def ingest_cycle(ctx: object) -> None:
    raise NotImplementedError
