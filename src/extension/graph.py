"""Builds the draft -> review -> finalize graph with the request_changes/reject/
approve routing."""

from langgraph.graph.state import CompiledStateGraph

from extension.state import State


def route_after_review(state: State) -> str:
    raise NotImplementedError


def build(deps: object) -> CompiledStateGraph[State]:
    raise NotImplementedError
