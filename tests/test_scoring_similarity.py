"""Offline tests for the vector stage. Ollama is faked; the one database test skips when
no Postgres is reachable, following tests/conftest.py."""

from typing import Any

import numpy as np
import psycopg
import pytest
from psycopg.rows import DictRow
from pydantic import HttpUrl

from domain.offer import Offer
from scoring import similarity
from scoring.similarity import (
    EMBEDDING_DIMENSIONS,
    MAX_OFFER_TEXT_CHARS,
    cos_sim,
    embed,
    knn_score,
    offer_text,
    similarity_score,
)


class _FakeResponse:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self.embeddings = embeddings


class _FakeClient:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self._embeddings = embeddings
        self.calls: list[dict[str, Any]] = []

    async def embed(self, model: str, input: str, truncate: bool) -> _FakeResponse:
        self.calls.append({"model": model, "input": input, "truncate": truncate})
        return _FakeResponse(self._embeddings)


def _use_client(monkeypatch: pytest.MonkeyPatch, client: _FakeClient) -> None:
    monkeypatch.setattr(similarity, "_get_client", lambda: client)


def _offer(**kwargs: Any) -> Offer:
    defaults: dict[str, Any] = {
        "source": "test",
        "external_id": "1",
        "url": HttpUrl("https://example.test/1"),
        "title": "Senior Full-stack Developer",
    }
    return Offer(**(defaults | kwargs))


async def test_embed_returns_a_float64_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_client(monkeypatch, _FakeClient([[0.5] * EMBEDDING_DIMENSIONS]))
    vector = await embed("anything")
    assert vector.shape == (EMBEDDING_DIMENSIONS,)
    assert vector.dtype == np.float64


async def test_embed_never_lets_ollama_truncate(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default drops text past the context window and still returns a vector."""
    client = _FakeClient([[0.5] * EMBEDDING_DIMENSIONS])
    _use_client(monkeypatch, client)
    await embed("anything")
    assert client.calls[0]["truncate"] is False


async def test_embed_rejects_a_wrong_dimension_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """Caught here rather than at INSERT, where the message would name psycopg."""
    _use_client(monkeypatch, _FakeClient([[0.5] * 512]))
    with pytest.raises(ValueError, match="512 dimensions"):
        await embed("anything")


async def test_embed_raises_when_ollama_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_client(monkeypatch, _FakeClient([]))
    with pytest.raises(RuntimeError, match="no embedding"):
        await embed("anything")


def test_offer_text_puts_the_high_signal_fields_before_the_description() -> None:
    """Field order decides what survives the length cap."""
    text = offer_text(
        _offer(company="Acme", technologies=["React", "Node.js"], description="Long prose.")
    )
    assert text.index("React") < text.index("Long prose.")
    assert text.index("Senior Full-stack Developer") < text.index("React")


def test_offer_text_survives_a_missing_company() -> None:
    assert "Senior Full-stack Developer" in offer_text(_offer(company=None))


def test_offer_text_caps_length() -> None:
    assert len(offer_text(_offer(description="x" * 20_000))) == MAX_OFFER_TEXT_CHARS


def test_cos_sim_scores_identical_opposite_and_orthogonal_vectors() -> None:
    a = np.array([1.0, 0.0, 0.0])
    assert cos_sim(a, a) == pytest.approx(1.0)
    assert cos_sim(a, np.array([-1.0, 0.0, 0.0])) == pytest.approx(-1.0)
    assert cos_sim(a, np.array([0.0, 1.0, 0.0])) == pytest.approx(0.0)


def test_cos_sim_answers_zero_for_an_unnormalisable_vector() -> None:
    """nan compares false against every threshold, giving a silent reject."""
    result = cos_sim(np.array([1.0, 2.0, 3.0]), np.zeros(3))
    assert result == 0.0
    assert not np.isnan(result)


def test_similarity_score_reports_no_preference_data_as_none() -> None:
    """None, not 0.0: no data yet is not the same as a bad match."""
    scores = similarity_score(np.ones(3), np.ones(3))
    assert scores["profile_similarity"] == pytest.approx(1.0)
    assert scores["preference_similarity"] is None


async def test_knn_score_returns_none_below_k_ratings(
    conn: psycopg.AsyncConnection[DictRow],
) -> None:
    """Fewer than k ratings makes k-NN an average of everything, not a local signal."""
    assert await knn_score(conn, np.zeros(EMBEDDING_DIMENSIONS), k=7) is None
