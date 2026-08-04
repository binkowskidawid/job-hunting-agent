"""Vector similarity — profile match (from day one) and preference match (grows with
your ratings). Free, computed locally via Ollama."""

from typing import Any

import numpy as np
import numpy.typing as npt

from domain.offer import Offer

EMBEDDING_MODEL = "nomic-embed-text"


def embed(text: str) -> npt.NDArray[np.float64]:
    raise NotImplementedError


def offer_text(offer: Offer) -> str:
    raise NotImplementedError


def cos_sim(a: npt.NDArray[np.float64], b: npt.NDArray[np.float64]) -> float:
    raise NotImplementedError


def similarity_score(
    offer_vector: npt.NDArray[np.float64], profile: dict[str, Any]
) -> dict[str, Any]:
    raise NotImplementedError


async def knn_score(
    conn: object, vector: npt.NDArray[np.float64], k: int = 7
) -> dict[str, Any] | None:
    raise NotImplementedError
