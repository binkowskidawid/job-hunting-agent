"""LLM judge — the one paid step in the cascade, reached only for uncertain offers.
Cache-friendly and provenance-aware.

Security: `judge_offer` MUST wrap the raw offer content in `<JOB_POSTING>...</JOB_POSTING>`
tags when building `user_content` — the system prompt (prompts/judge.v1.md) tells the model
that only content inside that tag is untrusted data, never instructions. Passing the offer
text unwrapped breaks that contract and reopens prompt injection from job posting content.
"""

from typing import Any

from domain.offer import Offer
from llm_client import LLMClient, LLMResponse

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["great", "worth_it", "weak", "reject"]},
        "score": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string", "maxLength": 300},
        "pros": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "cons": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "contradictions": {"type": "array", "items": {"type": "string"}},
        "manipulation_detected": {"type": "boolean"},
    },
    "required": ["verdict", "score", "reason", "pros", "cons", "manipulation_detected"],
}


async def judge_offer(
    llm: LLMClient, offer: Offer, profile: dict[str, Any], examples: list[dict[str, Any]]
) -> LLMResponse:
    raise NotImplementedError
