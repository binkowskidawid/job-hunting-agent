"""The whole cascade, with the two paid or networked stages faked: Ollama and Anthropic never
get called, so these run offline.

The filter runs for real. Wiring it to the decision through a mock would test the mock.
"""

import json
from typing import Any, cast
from uuid import UUID, uuid4

import numpy as np
import numpy.typing as npt
import psycopg
import pytest
from psycopg.rows import DictRow
from pydantic import HttpUrl

from candidate.config import Filters, Profile
from domain.offer import Offer
from llm_client import LLMClient, LLMResponse
from scoring import cascade
from scoring.cascade import VERSION, ScoringContext, score
from scoring.judge import JudgeVerdict
from scoring.similarity import EMBEDDING_DIMENSIONS

PROFILE = Profile.model_validate(
    {
        "target_roles": ["Full-stack Developer"],
        "years_experience": 6,
        "competencies": [{"name": "TypeScript", "level": "expert"}],
    }
)

FILTERS = Filters.model_validate(
    {
        "salary": {"min_b2b_month": 10_000, "missing_range": "flag"},
        "work_mode": {"accepted": ["remote"]},
        "contract_type": {"accepted": ["b2b"]},
        "level": {"reject_outright": ["junior"]},
        "stop_words": {"title": ["QA"]},
        "technologies": {
            "required_at_least_one": ["TypeScript"],
            "big_plus": ["Docker", "LLM", "Next.js", "PostgreSQL"],
            "minus": ["PHP", "Angular", "Vue", "jQuery"],
            "veto": [".NET"],
        },
    }
)

PROFILE_VECTOR = np.ones(EMBEDDING_DIMENSIONS, dtype=np.float64)
ORTHOGONAL = np.array([1.0, -1.0] * (EMBEDDING_DIMENSIONS // 2), dtype=np.float64)

VERDICT = JudgeVerdict(
    verdict="worth_it",
    score=0.66,
    reason="Modern stack, vague scope.",
    pros=["Remote"],
    cons=["No team size"],
    contradictions=[],
    manipulation_detected=False,
)

LLM_RESPONSE = LLMResponse(
    data={},
    text="",
    cost_usd=0.0031,
    tokens_in=900,
    tokens_out=120,
    latency_ms=800,
    model="claude-haiku-4-5",
)


class FakeConn:
    """Records SQL instead of running it. score() reads nothing back, so nothing is faked."""

    def __init__(self) -> None:
        self.queries: list[tuple[str, Any]] = []

    async def execute(self, query: str, params: Any = None) -> None:
        self.queries.append((query, params))

    def inserted_score(self) -> dict[str, Any]:
        return next(params for query, params in self.queries if "INSERT INTO offer_score" in query)

    def embedding_updates(self) -> list[Any]:
        return [params for query, params in self.queries if "SET embedding" in query]


def make_offer(**overrides: Any) -> Offer:
    fields: dict[str, Any] = {
        "source": "test",
        "external_id": "1",
        "url": HttpUrl("https://example.test/1"),
        "title": "Senior Full-stack Developer",
        "description": "TypeScript everywhere.",
        "work_mode": "remote",
        "contract_type": "b2b",
        "salary_max": 10_000,
        "period": "month",
    }
    return Offer(**(fields | overrides))


def make_ctx(n_ratings: int = 0) -> ScoringContext:
    return ScoringContext(
        llm=cast(LLMClient, object()),
        profile=PROFILE,
        filters=FILTERS,
        profile_vector=PROFILE_VECTOR,
        n_ratings=n_ratings,
    )


@pytest.fixture
def stubs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Everything that would touch Ollama or Anthropic, replaced by default."""
    state: dict[str, Any] = {"vector": PROFILE_VECTOR, "knn": None, "judge": VERDICT, "judged": 0}

    async def fake_embed(text: str) -> npt.NDArray[np.float64]:
        return cast(npt.NDArray[np.float64], state["vector"])

    async def fake_knn(conn: Any, vector: Any, k: int = 7) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, state["knn"])

    async def fake_judge(*args: Any) -> tuple[JudgeVerdict, LLMResponse]:
        state["judged"] += 1
        return cast(JudgeVerdict, state["judge"]), LLM_RESPONSE

    monkeypatch.setattr(cascade, "embed", fake_embed)
    monkeypatch.setattr(cascade, "knn_score", fake_knn)
    monkeypatch.setattr(cascade, "judge_offer", fake_judge)
    return state


async def run(offer: Offer, ctx: ScoringContext | None = None) -> tuple[dict[str, Any], FakeConn]:
    conn = FakeConn()
    result = await score(
        cast(psycopg.AsyncConnection[DictRow], conn), ctx or make_ctx(), uuid4(), offer
    )
    return result, conn


# An offer that clears the filter and every signal: 4 plus technologies, no minuses, double
# the salary floor, and an embedding identical to the profile.
SEND_OFFER = {"description": "TypeScript, Docker, LLM, Next.js, PostgreSQL.", "salary_max": 20_000}
# Same filter outcome, every signal at the floor.
REJECT_OFFER = {"description": "TypeScript, PHP, Angular, Vue, jQuery."}


class TestFilterStage:
    async def test_a_filtered_offer_never_reaches_the_embedder(self, stubs: dict[str, Any]) -> None:
        """Stage 1 is free and stage 2 is not. Ordering is the thesis of the project."""
        _, conn = await run(make_offer(title="QA Engineer"))
        assert conn.embedding_updates() == []

    async def test_a_filtered_offer_is_persisted_with_its_reason(self) -> None:
        """Rejections are the only record of what the system threw away."""
        _, conn = await run(make_offer(title="QA Engineer"))
        row = conn.inserted_score()
        assert row["rejection_stage"] == "filter"
        assert "QA" in row["rejection_reason"]

    async def test_a_filtered_offer_costs_nothing(self) -> None:
        result, _ = await run(make_offer(title="QA Engineer"))
        assert result == {"decision": "reject", "stage": "filter", "score": None, "cost_usd": 0.0}

    async def test_filter_features_are_persisted_even_on_rejection(self) -> None:
        _, conn = await run(make_offer(description="TypeScript.", salary_max=100))
        features = json.loads(conn.inserted_score()["features"])
        assert features["salary_pln_month"] == 100


class TestVectorStage:
    async def test_a_strong_offer_is_sent_without_paying_the_judge(
        self, stubs: dict[str, Any]
    ) -> None:
        result, _ = await run(make_offer(**SEND_OFFER))
        assert result["decision"] == "send"
        assert result["stage"] == "vector"
        assert stubs["judged"] == 0

    async def test_a_weak_offer_is_rejected_without_paying_the_judge(
        self, stubs: dict[str, Any]
    ) -> None:
        stubs["vector"] = ORTHOGONAL
        result, conn = await run(make_offer(**REJECT_OFFER))
        assert result["decision"] == "reject"
        assert stubs["judged"] == 0
        assert conn.inserted_score()["rejection_stage"] == "vector"

    async def test_a_vector_rejection_records_the_score_it_fell_short_of(
        self, stubs: dict[str, Any]
    ) -> None:
        stubs["vector"] = ORTHOGONAL
        _, conn = await run(make_offer(**REJECT_OFFER))
        assert "0.000" in conn.inserted_score()["rejection_reason"]

    async def test_the_embedding_is_stored_for_later_neighbours(
        self, stubs: dict[str, Any]
    ) -> None:
        """knn_score joins on offer.embedding; nothing else writes that column."""
        _, conn = await run(make_offer(**SEND_OFFER))
        assert len(conn.embedding_updates()) == 1

    async def test_an_available_knn_is_recorded(self, stubs: dict[str, Any]) -> None:
        stubs["knn"] = {"knn": 0.8, "knn_n": 7}
        _, conn = await run(make_offer(**SEND_OFFER), make_ctx(n_ratings=10))
        assert conn.inserted_score()["knn_score"] == 0.8


class TestJudgeStage:
    async def test_an_uncertain_offer_reaches_the_judge(self, stubs: dict[str, Any]) -> None:
        result, _ = await run(make_offer())
        assert result["stage"] == "judge"
        assert stubs["judged"] == 1

    async def test_the_judge_cost_is_recorded(self, stubs: dict[str, Any]) -> None:
        """Never skip logging cost 'to save time on a prototype'."""
        result, conn = await run(make_offer())
        assert result["cost_usd"] == pytest.approx(0.0031)
        assert conn.inserted_score()["cost_usd"] == pytest.approx(0.0031)

    async def test_the_judge_verdict_replaces_the_vector_score(self, stubs: dict[str, Any]) -> None:
        _, conn = await run(make_offer())
        row = conn.inserted_score()
        assert row["llm_score"] == 0.66
        assert row["final_score"] == 0.66
        assert row["rationale"] == "Modern stack, vague scope."

    async def test_a_weak_verdict_becomes_a_rejection(self, stubs: dict[str, Any]) -> None:
        stubs["judge"] = VERDICT.model_copy(update={"verdict": "weak"})
        result, conn = await run(make_offer())
        assert result["decision"] == "reject"
        assert conn.inserted_score()["rejection_stage"] == "judge"

    async def test_a_posting_that_manipulates_the_judge_is_rejected(
        self, stubs: dict[str, Any]
    ) -> None:
        """A posting addressing the model is evidence about the poster, whatever it scored."""
        stubs["judge"] = VERDICT.model_copy(update={"manipulation_detected": True})
        result, conn = await run(make_offer())
        assert result["decision"] == "reject"
        assert "manipulation" in conn.inserted_score()["rejection_reason"]


class TestProvenance:
    async def test_every_row_carries_the_scoring_version(self, stubs: dict[str, Any]) -> None:
        """Without it, rows scored by two different cascades are indistinguishable later."""
        _, conn = await run(make_offer(**SEND_OFFER))
        assert conn.inserted_score()["scoring_version"] == VERSION

    async def test_the_filter_never_produces_a_rule_score(self, stubs: dict[str, Any]) -> None:
        _, conn = await run(make_offer(**SEND_OFFER))
        assert conn.inserted_score()["rule_score"] is None


async def test_the_row_lands_in_postgres(
    conn: psycopg.AsyncConnection[DictRow], stubs: dict[str, Any]
) -> None:
    """Integration: the column list and types must match the live schema, not just each other."""
    offer = make_offer(title="QA Engineer")
    row = await (
        await conn.execute(
            """
            INSERT INTO offer (source, external_id, identity_key, url, payload)
            VALUES ('test', %s, 'k', %s, '{}') RETURNING id
            """,
            (str(uuid4()), str(offer.url)),
        )
    ).fetchone()
    assert row is not None

    result = await score(conn, make_ctx(), cast(UUID, row["id"]), offer)
    assert result["decision"] == "reject"

    stored = await (
        await conn.execute(
            "SELECT rejection_stage, rejection_reason, scoring_version FROM offer_score "
            "WHERE offer_id = %s",
            (row["id"],),
        )
    ).fetchone()
    assert stored is not None
    assert stored["rejection_stage"] == "filter"
    assert stored["scoring_version"] == VERSION
