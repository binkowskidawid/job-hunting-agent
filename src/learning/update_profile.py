"""Ties the learning mechanisms together: recompute centroids, pick weights/thresholds
for the current stage, calibrate once you have enough ratings, detect drift."""

from typing import Any


async def detect_drift(conn: object, window_days: int = 30) -> dict[str, Any] | None:
    raise NotImplementedError


async def update_profile(conn: object) -> dict[str, Any]:
    raise NotImplementedError
