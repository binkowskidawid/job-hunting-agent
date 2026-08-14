"""Covers the parts of LLMClient that hold without a network call: the contract later
modules import against, cost arithmetic, and schema rewriting for strict tool use."""

import inspect

import pytest
from pydantic import BaseModel, Field

import llm_client
from llm_client import LLMClient, LLMResponse, StructuredOutputError, json_schema


def test_llm_response_has_expected_fields() -> None:
    fields = {f for f in LLMResponse.__dataclass_fields__}
    assert fields == {"data", "text", "cost_usd", "tokens_in", "tokens_out", "latency_ms", "model"}


def test_llm_client_structured_signature() -> None:
    sig = inspect.signature(LLMClient.structured)
    assert list(sig.parameters) == [
        "self",
        "system",
        "user_content",
        "tool_name",
        "schema",
        "tool_description",
        "model",
        "cache_system",
    ]


def test_json_schema_is_callable() -> None:
    assert callable(json_schema)


class _Nested(BaseModel):
    label: str


class _Sample(BaseModel):
    name: str = Field(max_length=50)
    score: int = Field(ge=0, le=100)
    note: str | None = None
    nested: _Nested


def test_json_schema_closes_every_object_including_nested_defs() -> None:
    schema = json_schema(_Sample)

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["_Nested"]["additionalProperties"] is False


def test_json_schema_requires_every_property_even_optional_ones() -> None:
    """`note` has a default, so Pydantic leaves it out of `required` — strict mode won't."""
    schema = json_schema(_Sample)

    assert set(schema["required"]) == {"name", "score", "note", "nested"}


def test_json_schema_drops_keys_the_api_rejects() -> None:
    schema = json_schema(_Sample)
    flat = str(schema)

    for banned in ("maxLength", "minimum", "maximum", "title"):
        assert banned not in flat


def test_cost_prices_each_token_class_at_its_own_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    """One million of each class, so every term reads as its own multiplier."""
    monkeypatch.setitem(llm_client.PRICING, "test-model", (10.0, 50.0))

    cost = LLMClient._cost(
        "test-model",
        tokens_in=1_000_000,
        tokens_out=1_000_000,
        cache_read=1_000_000,
        cache_write=1_000_000,
    )

    assert cost == pytest.approx(10.0 + 1.0 + 12.5 + 50.0)


def test_cost_of_unknown_model_is_zero_not_an_error() -> None:
    assert LLMClient._cost("no-such-model", tokens_in=1_000, tokens_out=1_000) == 0.0


def test_require_tool_input_passes_through_a_filled_payload() -> None:
    payload = {"verdict": "great", "confidence": 0.9}

    assert LLMClient._require_tool_input(payload, "claude-sonnet-5", "tool_use") == payload


def test_require_tool_input_raises_and_keeps_the_stop_reason() -> None:
    """The stop_reason is the whole diagnostic value — it must survive the raise."""
    with pytest.raises(StructuredOutputError) as caught:
        LLMClient._require_tool_input(None, "claude-sonnet-5", "max_tokens")

    assert caught.value.stop_reason == "max_tokens"
    assert "claude-sonnet-5" in str(caught.value)
