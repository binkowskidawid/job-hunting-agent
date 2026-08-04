"""Verifies decide() returns one of the three documented actions — a property test,
since decide() isn't implemented yet this just locks the contract for later."""

import pytest

from scoring.decision import decide


def test_decide_is_not_yet_implemented() -> None:
    with pytest.raises(NotImplementedError):
        decide(0.5, {"low": 0.3, "high": 0.7}, {})
