"""Verifies the LLMClient stub has the exact shape later modules depend on — not its
behavior, which isn't implemented yet."""

import inspect

from llm_client import LLMClient, LLMResponse, json_schema


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
