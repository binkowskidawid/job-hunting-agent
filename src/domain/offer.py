"""Normalized job offer — the common shape every source adapter returns."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class ContractType(StrEnum):
    B2B = "b2b"
    EMPLOYMENT_CONTRACT = "employment_contract"
    MANDATE_CONTRACT = "mandate_contract"
    UNKNOWN = "unknown"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class Offer(BaseModel):
    """Normalized job offer shared by every source adapter."""

    source: str
    external_id: str
    url: HttpUrl
    title: str
    company: str | None = None
    description: str = ""

    salary_min: int | None = None
    salary_max: int | None = None
    currency: str = "PLN"
    period: str | None = None
    contract_type: ContractType = ContractType.UNKNOWN

    work_mode: WorkMode = WorkMode.UNKNOWN
    locations: list[str] = []
    technologies: list[str] = []
    level: str | None = None

    published_at: date | None = None
    fetched_at: datetime = Field(default_factory=datetime.now)
    raw_content: dict[str, Any] = {}
    # This model is intentionally complete as a schema — the work left is in
    # sources/*.py: building Offer instances from real adapters.
