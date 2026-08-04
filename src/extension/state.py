"""LangGraph state — flat and serializable, checkpointed to Postgres after every
step."""

import operator
from typing import Annotated, Any, TypedDict


class State(TypedDict):
    offer_id: str
    offer: dict[str, Any]
    cv_summary: str
    draft: dict[str, Any] | None
    draft_version: int
    decision: dict[str, Any] | None
    final_message: str | None
    trace: Annotated[list[dict[str, Any]], operator.add]
    cost_usd: Annotated[float, operator.add]
