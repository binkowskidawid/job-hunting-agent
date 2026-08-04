"""Graph nodes: draft (wraps the manual agent loop), review (the interrupt() point —
MUST be the first statement in the function body), finalize."""

from collections.abc import Callable
from typing import Any

from extension.state import State


def draft_node(deps: object) -> Callable[[State], dict[str, Any]]:
    def run(state: State) -> dict[str, Any]:
        raise NotImplementedError
    return run


def review_node(state: State) -> dict[str, Any]:
    raise NotImplementedError


def finalize_node(deps: object) -> Callable[[State], dict[str, Any]]:
    def run(state: State) -> dict[str, Any]:
        raise NotImplementedError
    return run
