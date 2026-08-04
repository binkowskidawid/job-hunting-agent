"""CV -> structured competency profile, with provenance (confidence + a verbatim quote
backing each assessed skill level)."""

from pydantic import BaseModel, Field


class Competency(BaseModel):
    name: str
    level: str = Field(description="expert | proficient | basic | familiar")
    years: float | None = None
    context: str = Field(description="Where you used this, one sentence")
    confidence: float = Field(ge=0.0, le=1.0)
    source_quote: str = Field(max_length=200)


class CVCompetencies(BaseModel):
    """Extracted from the CV once. Update it when you update your CV."""

    target_roles: list[str]
    years_experience: float
    competencies: list[Competency]
    domains: list[str]
    languages: list[str]
    differentiators: list[str]
