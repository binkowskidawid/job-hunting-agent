"""Hand-edited configuration: who you are, and what you will not accept.

Both files are written by you, not produced by a model. That is deliberate. The thresholds in
`filters.yaml` are decisions worth reading in a git diff, and a competency profile you wrote
yourself carries no confidence score or source quote — provenance exists to police a model,
and here you are the source.

Values that also appear on `Offer` are validated against the same enums the adapters produce,
so a typo like `remot` fails at startup instead of quietly rejecting every offer.
"""

from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from domain.offer import ContractType, WorkMode

CONFIG_DIR = Path(__file__).parent
PROFILE_PATH = CONFIG_DIR / "profile.yaml"
FILTERS_PATH = CONFIG_DIR / "filters.yaml"


class Level(StrEnum):
    EXPERT = "expert"
    PROFICIENT = "proficient"
    BASIC = "basic"
    FAMILIAR = "familiar"


class Competency(BaseModel):
    name: str
    level: Level
    years: float | None = None
    context: str = Field(default="", description="Where you used this, one or two sentences")


class Profile(BaseModel):
    """What the cascade compares every offer against on day one."""

    target_roles: list[str]
    years_experience: float
    competencies: list[Competency]
    domains: list[str] = []
    languages: list[str] = []
    differentiators: list[str] = []

    def as_text(self) -> str:
        """Render the profile as the text that gets embedded and shown to the judge.

        `context` carries most of the meaning — "Python" alone barely separates two backend
        roles, while the sentence describing what you did with it does.
        """
        lines = [f"Target roles: {', '.join(self.target_roles)}"]
        lines.append(f"Experience: {self.years_experience:g} years")
        if self.domains:
            lines.append(f"Domains: {', '.join(self.domains)}")
        lines.append("Competencies:")
        for c in self.competencies:
            years = f", {c.years:g} years" if c.years is not None else ""
            context = f" — {c.context.strip()}" if c.context.strip() else ""
            lines.append(f"- {c.name} ({c.level}{years}){context}")
        if self.differentiators:
            lines.append("Differentiators:")
            lines.extend(f"- {d}" for d in self.differentiators)
        return "\n".join(lines)


class SalaryFilter(BaseModel):
    min_b2b_month: int = 0
    min_employment_month: int = 0
    min_hourly_b2b: int = 0
    missing_range: Literal["reject", "pass", "flag"] = "flag"


class WorkModeFilter(BaseModel):
    accepted: list[WorkMode] = []
    hybrid_allowed_cities: list[str] = []


class ContractFilter(BaseModel):
    accepted: list[ContractType] = []
    preferred: ContractType | None = None


class LevelFilter(BaseModel):
    accepted: list[str] = []
    reject_outright: list[str] = []


class StopWords(BaseModel):
    title: list[str] = []
    description: list[str] = []


class TechnologyFilter(BaseModel):
    required_at_least_one: list[str] = []
    big_plus: list[str] = []
    neutral: list[str] = []
    minus: list[str] = []
    veto: list[str] = []


class Filters(BaseModel):
    salary: SalaryFilter = SalaryFilter()
    work_mode: WorkModeFilter = WorkModeFilter()
    contract_type: ContractFilter = ContractFilter()
    level: LevelFilter = LevelFilter()
    stop_words: StopWords = StopWords()
    technologies: TechnologyFilter = TechnologyFilter()


def _load[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    if not path.exists():
        example = path.with_suffix(".example.yaml")
        raise FileNotFoundError(f"{path} is missing — copy {example.name} to it and fill it in.")
    # safe_load, never load: these files are configuration, and loading configuration must not
    # be able to construct arbitrary Python objects.
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{path.name} is invalid:\n{exc}") from exc


def load_profile(path: Path = PROFILE_PATH) -> Profile:
    return _load(path, Profile)


def load_filters(path: Path = FILTERS_PATH) -> Filters:
    return _load(path, Filters)
