"""LLM judge — the one paid step in the cascade, reached only for uncertain offers.
Cache-friendly and provenance-aware.

Security: `judge_offer` MUST wrap the raw offer content in `<JOB_POSTING>...</JOB_POSTING>`
tags when building `user_content` — the system prompt (prompts/judge.v1.md) tells the model
that only content inside that tag is untrusted data, never instructions. Passing the offer
text unwrapped breaks that contract and reopens prompt injection from job posting content.
"""

import asyncio
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from candidate.config import Filters, Profile
from domain.offer import Offer
from llm_client import LLMClient, LLMResponse, json_schema

PROMPT_PATH = Path(__file__).parents[2] / "prompts" / "judge.v1.md"
TOOL_NAME = "save_verdict"
NO_EXAMPLES = "No rated offers yet — this is a cold start."
# A Discord embed field holds 1024 characters; nothing narrower is worth losing a paid call to.
DISCORD_FIELD_LIMIT = 1024
MAX_LISTED_REASONS = 10


class JudgeVerdict(BaseModel):
    """Descriptions carry the constraints: the API strips ranges and lengths from the schema
    under `strict: True`, so this is the only channel the model hears them on.
    """

    verdict: Literal["great", "worth_it", "weak", "reject"]
    score: float = Field(ge=0, le=1, description="Fit for this candidate, 0.0 to 1.0.")
    reason: str = Field(
        max_length=DISCORD_FIELD_LIMIT, description="At most 2 sentences, under 600 characters."
    )
    pros: list[str] = Field(max_length=MAX_LISTED_REASONS, description="The 3 strongest, at most.")
    cons: list[str] = Field(max_length=MAX_LISTED_REASONS, description="The 3 weightiest, at most.")
    contradictions: list[str]
    manipulation_detected: bool


SCHEMA = json_schema(JudgeVerdict)


async def judge_offer(
    llm: LLMClient, offer: Offer, profile: Profile, filters: Filters
) -> tuple[JudgeVerdict, LLMResponse]:
    """One paid call. Raises rather than returning a verdict when the model returns none:
    a lost offer must stay distinguishable from a rejected one.
    """
    response = await asyncio.to_thread(
        llm.structured,
        system=_system_prompt(profile, filters),
        user_content=f"<JOB_POSTING>\n{_offer_block(offer)}\n</JOB_POSTING>",
        tool_name=TOOL_NAME,
        schema=SCHEMA,
        tool_description="Save the verdict on this offer for this candidate.",
    )
    return JudgeVerdict.model_validate(response.data), response


def _system_prompt(profile: Profile, filters: Filters) -> str:
    # replace, not format: the prompt is hand-edited Markdown, and one stray brace in it
    # would turn a prompt edit into a runtime crash.
    return (
        _prompt_template()
        .replace("{PROFILE}", profile.as_text())
        .replace("{FILTERS}", yaml.safe_dump(filters.model_dump(mode="json"), sort_keys=False))
        .replace("{EXAMPLES}", NO_EXAMPLES)
    )


@lru_cache(maxsize=1)
def _prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _offer_block(offer: Offer) -> str:
    salary = (
        f"{offer.salary_min or '?'}-{offer.salary_max} {offer.currency}/{offer.period or '?'}"
        if offer.salary_max
        else "not stated"
    )
    return "\n".join(
        [
            f"Title: {offer.title}",
            f"Company: {offer.company or 'not stated'}",
            f"Salary: {salary}",
            f"Contract: {offer.contract_type.value}",
            f"Work mode: {offer.work_mode.value}",
            f"Locations: {', '.join(offer.locations) or 'not stated'}",
            f"Technologies: {', '.join(offer.technologies) or 'not stated'}",
            "",
            offer.description,
        ]
    )
