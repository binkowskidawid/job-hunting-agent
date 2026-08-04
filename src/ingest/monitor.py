"""Alerts when a source adapter goes silent longer than expected — a silent failure
here means you stop getting notifications and never find out why."""

from sources.base import Adapter


async def check_health(conn: object, adapter: Adapter) -> None:
    raise NotImplementedError
