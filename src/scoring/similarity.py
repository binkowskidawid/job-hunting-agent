"""Vector similarity: profile match from day one, k-NN against your own ratings."""

import os
from collections import Counter
from typing import Any

import numpy as np
import numpy.typing as npt
from ollama import AsyncClient
from psycopg import AsyncConnection
from psycopg.rows import DictRow

from domain.offer import Offer
from learning.centroids import RATING_WEIGHTS

EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBEDDING_DIMENSIONS = 768  # must match vector(768) in migrations/001_init.sql
MAX_OFFER_TEXT_CHARS = 4000  # 2048-token context, measured at ~2.4 characters per token
_REQUEST_TIMEOUT_S = 60.0

_client: AsyncClient | None = None


def _get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = AsyncClient(timeout=_REQUEST_TIMEOUT_S)
    return _client


async def embed(text: str) -> npt.NDArray[np.float64]:
    """Embed one text through Ollama."""
    # truncate=False: the default drops text past the context window and still returns a
    # well-formed vector.
    response = await _get_client().embed(model=EMBEDDING_MODEL, input=text, truncate=False)
    if not response.embeddings:
        raise RuntimeError(f"Ollama returned no embedding for model {EMBEDDING_MODEL!r}")

    vector = np.asarray(response.embeddings[0], dtype=np.float64)
    if vector.shape != (EMBEDDING_DIMENSIONS,):
        raise ValueError(
            f"Model {EMBEDDING_MODEL!r} returned {vector.shape[0]} dimensions, "
            f"expected {EMBEDDING_DIMENSIONS}"
        )
    return vector


def offer_text(offer: Offer) -> str:
    """Render an offer as the text compared against `Profile.as_text()`.

    Title and technologies lead because the description absorbs the length cap. Salary and
    location are omitted: the rule filter already checked them numerically.
    """
    text = "\n".join(
        [offer.title, offer.company or "", " ".join(offer.technologies), offer.description]
    )
    return text[:MAX_OFFER_TEXT_CHARS]


def cos_sim(a: npt.NDArray[np.float64], b: npt.NDArray[np.float64]) -> float:
    """Cosine similarity, answering 0.0 rather than nan for an unnormalisable vector."""
    norms = float(np.linalg.norm(a) * np.linalg.norm(b))
    if norms == 0.0:
        return 0.0
    return float(np.dot(a, b) / norms)


def similarity_score(
    offer_vector: npt.NDArray[np.float64], profile_vector: npt.NDArray[np.float64]
) -> dict[str, Any]:
    """Takes the profile already embedded; it is constant for a whole ingest cycle."""
    return {
        "profile_similarity": cos_sim(offer_vector, profile_vector),
        "preference_similarity": None,
    }


def _vector_literal(vector: npt.NDArray[np.float64]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


def _rating_scale_to_unit(value: float) -> float:
    """RATING_WEIGHTS spans [-1, 1]; every other signal spans [0, 1]."""
    return (value + 1.0) / 2.0


async def knn_score(
    conn: AsyncConnection[DictRow], vector: npt.NDArray[np.float64], k: int = 7
) -> dict[str, Any] | None:
    """How the k offers most similar to this one were rated. None below k ratings."""
    literal = _vector_literal(vector)
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT r.rating, 1 - (o.embedding <=> %s::vector) AS similarity
            FROM my_rating r
            JOIN offer o ON o.id = r.offer_id
            WHERE o.embedding IS NOT NULL
            ORDER BY o.embedding <=> %s::vector
            LIMIT %s
            """,
            (literal, literal, k),
        )
        neighbours = await cur.fetchall()

    if len(neighbours) < k:
        return None

    nearest = [
        (RATING_WEIGHTS[row["rating"]], row["similarity"])
        for row in neighbours
        if row["similarity"] > 0.0
    ]
    if not nearest:
        return None

    weighted = sum(weight * similarity for weight, similarity in nearest) / sum(
        similarity for _, similarity in nearest
    )

    return {
        "knn": _rating_scale_to_unit(float(weighted)),
        "knn_n": len(nearest),
        "knn_ratings": dict(Counter(row["rating"] for row in neighbours)),
        "knn_scores": [float(row["similarity"]) for row in neighbours],
    }
