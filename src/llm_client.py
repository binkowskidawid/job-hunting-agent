"""Thin wrapper over the Anthropic SDK: forced structured output, cost tracking, prompt
caching. Every LLM call in this project goes through LLMClient — never call the SDK
directly from feature code."""

import logging
import time
from dataclasses import dataclass
from typing import Any, cast

import anthropic
from pydantic import BaseModel

log = logging.getLogger(__name__)

# Prices in USD per million tokens — filled in only once verified against the current
# provider pricing page. Never hand-type a number here from memory.
# Verified 2026-08-14 against https://platform.claude.com/docs/en/about-claude/pricing
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

CACHE_READ_MULTIPLIER = 0.1
# 1h TTL is 2.0 — keep in sync with cache_control in structured()
CACHE_WRITE_MULTIPLIER_5M = 1.25

# Rejected by the API under strict mode; ranges stay enforced client-side by Pydantic.
UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
    }
)

MAX_TOKENS = 8000
# Haiku 4.5 rejects output_config.effort outright; the 5-series accepts low..max.
EFFORT_CAPABLE = frozenset({"claude-opus-5", "claude-sonnet-5"})
DEFAULT_EFFORT = "low"


class StructuredOutputError(RuntimeError):
    """The call succeeded but carried no tool arguments.

    This is a judge failure, never a verdict — callers must persist it as such so a
    lost offer stays distinguishable from a rejected one.
    """

    def __init__(self, model: str, stop_reason: str | None) -> None:
        super().__init__(f"{model} returned no tool input (stop_reason={stop_reason})")
        self.stop_reason = stop_reason


@dataclass
class LLMResponse:
    data: dict[str, Any]
    text: str
    cost_usd: float
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model: str


class LLMClient:
    def __init__(self, model: str) -> None:
        self.model = model
        self.client = anthropic.Anthropic()

    @staticmethod
    def _cost(
        model: str,
        tokens_in: int,
        tokens_out: int,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> float:
        """USD for one call. `tokens_in` is the uncached remainder, not the prompt total.

        Three input prices, one output price, each in USD per million tokens:
            - tokens_in    -> full price of input tokens
            - cache_read   -> ~0.1x input price
            - cache_write  -> ~1.25x input price (TTL 5 min)
            Unknown model -> 0.0 instead of KeyError; cost is logged, not enforced.
        """
        price_in, price_out = PRICING.get(model, (0.0, 0.0))
        tokens_in_cost = tokens_in * price_in
        cache_read_cost = cache_read * price_in * CACHE_READ_MULTIPLIER
        cache_write_cost = cache_write * price_in * CACHE_WRITE_MULTIPLIER_5M
        tokens_out_cost = tokens_out * price_out
        return (tokens_in_cost + cache_read_cost + cache_write_cost + tokens_out_cost) / 1_000_000

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
        """One forced tool call, so the reply is arguments matching `schema` — or nothing.

        Raises StructuredOutputError when the model produced no tool arguments.
        """
        model = model or self.model
        started = time.perf_counter()

        system_block: list[Any] = [{"type": "text", "text": system}]
        if cache_system:
            system_block[0]["cache_control"] = {"type": "ephemeral"}

        # Sent only where supported — see EFFORT_CAPABLE.
        tuning: dict[str, Any] = {}
        if model in EFFORT_CAPABLE:
            tuning["output_config"] = {"effort": DEFAULT_EFFORT}

        msg = self.client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_block,
            tools=[
                {
                    "name": tool_name,
                    "description": tool_description or "Save the analysis result per the schema.",
                    "input_schema": schema,
                    "strict": True,
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user_content}],
            **tuning,
        )

        data: dict[str, Any] | None = None
        text = ""
        for block in msg.content:
            if block.type == "tool_use" and block.name == tool_name:
                # The SDK types tool_use.input as `object`; the forced schema makes it a dict.
                data = cast(dict[str, Any], block.input)
            elif block.type == "text":
                text += block.text

        usage = msg.usage
        cache_read = usage.cache_read_input_tokens or 0
        cache_write = usage.cache_creation_input_tokens or 0
        cost = self._cost(model, usage.input_tokens, usage.output_tokens, cache_read, cache_write)
        latency_ms = int((time.perf_counter() - started) * 1000)

        log.info(
            "llm %s in=%d out=%d cache_read=%d cache_write=%d %.5f USD %dms",
            model,
            usage.input_tokens,
            usage.output_tokens,
            cache_read,
            cache_write,
            cost,
            latency_ms,
        )

        tool_input = self._require_tool_input(data, model, msg.stop_reason)

        return LLMResponse(
            data=tool_input,
            text=text,
            cost_usd=cost,
            tokens_in=usage.input_tokens,
            tokens_out=usage.output_tokens,
            latency_ms=latency_ms,
            model=model,
        )

    @staticmethod
    def _require_tool_input(
        data: dict[str, Any] | None,
        model: str,
        stop_reason: str | None,
    ) -> dict[str, Any]:
        """Return the tool arguments, or raise so a missing verdict cannot pass for one."""
        if data is None:
            raise StructuredOutputError(model, stop_reason)
        return data


def json_schema(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Pydantic model -> a JSON Schema the API accepts alongside `strict: True`."""
    # _strictify walks arbitrary JSON, so it is Any-in/Any-out; the root is always a dict.
    return cast(dict[str, Any], _strictify(model_cls.model_json_schema()))


def _strictify(node: Any) -> Any:
    """Walk a JSON Schema and rewrite every node to satisfy strict tool use.

    Mutates the tree in place — safe because Pydantic builds a fresh dict on each
    `model_json_schema()` call. Titles and range constraints are dropped; every object
    is closed and every property made required.
    """
    if isinstance(node, dict):
        for key in list(node.keys()):
            if key in UNSUPPORTED_SCHEMA_KEYS or key == "title":
                del node[key]
        if "properties" in node:
            node["additionalProperties"] = False
            # Strict mode admits no optional properties; a Pydantic default becomes an
            # explicit null the model has to choose, rather than a field it can skip.
            node["required"] = list(node["properties"].keys())
        for key, value in node.items():
            node[key] = _strictify(value)
    elif isinstance(node, list):
        return [_strictify(item) for item in node]
    return node
