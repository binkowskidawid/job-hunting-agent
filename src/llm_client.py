"""Thin wrapper over the Anthropic SDK: forced structured output, cost tracking, prompt
caching. Every LLM call in this project goes through LLMClient — never call the SDK
directly from feature code."""

from dataclasses import dataclass
from typing import Any

# Prices in USD per million tokens — filled in only once verified against the current
# provider pricing page. Never hand-type a number here from memory.
PRICING: dict[str, tuple[float, float]] = {}


@dataclass
class LLMResponse:
    data: dict[str, Any] | None
    text: str
    cost_usd: float
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model: str


class LLMClient:
    def __init__(self, model: str) -> None:
        self.model = model
        # TODO: construct anthropic.Anthropic() here

    def structured(
        self,
        system: str,
        user_content: str,
        tool_name: str,
        schema: dict[str, Any],
        tool_description: str = "",
        model: str | None = None,
        cache_system: bool = True,
    ) -> LLMResponse:
        raise NotImplementedError


def json_schema(model_cls: type) -> dict[str, Any]:
    raise NotImplementedError
