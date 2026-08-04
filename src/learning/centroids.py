"""Weighted, time-decayed centroids of your positively/negatively rated offers — the
simplest learning mechanism in the project."""

from typing import Any

import numpy as np
import numpy.typing as npt

RATING_WEIGHTS = {"great": 1.0, "maybe": 0.4, "pass": -0.6, "never_again": -1.0}


async def recompute_centroids(conn: object) -> dict[str, Any]:
    raise NotImplementedError


def multi_cluster_centroids(
    positive_vectors: npt.NDArray[np.float64], max_k: int = 3
) -> list[npt.NDArray[np.float64]]:
    raise NotImplementedError
