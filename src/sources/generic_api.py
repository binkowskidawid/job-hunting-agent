"""Adapter for an official source API — network hygiene (retry, backoff, honest
User-Agent) built into the base so it can't be skipped."""

import os
from typing import Any

import httpx

from sources.base import Adapter

CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "you@example.com")
USER_AGENT = f"JobAgent/1.0 (private single-user tool; contact: {CONTACT_EMAIL})"


class GenericApi(Adapter):
    name = "api-x"
    basis = "official_api"
    min_interval_s = 300

    async def _get(
        self, client: httpx.AsyncClient, url: str, attempts: int = 4
    ) -> dict[str, Any] | None:
        raise NotImplementedError
