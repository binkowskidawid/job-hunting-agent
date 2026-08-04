"""Cold-start solution: signal weights and decision thresholds shift as the number of
ratings grows."""

from typing import Any


def weights_for_stage(n_ratings: int) -> dict[str, Any]:
    raise NotImplementedError


def thresholds_for_stage(n_ratings: int) -> dict[str, Any]:
    raise NotImplementedError
