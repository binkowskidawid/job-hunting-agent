"""Weekly 15-minute ritual: sample rejected offers and check by hand whether the
cascade threw away anything good. The most important evaluation tool in the
project, precisely because it's manual."""

from typing import Any


async def audit_rejections(conn: object, n: int = 20) -> list[dict[str, Any]]:
    raise NotImplementedError
