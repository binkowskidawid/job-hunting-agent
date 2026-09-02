"""Glues the four stages together — the cost-aware pipeline this whole project is
built around."""

import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import numpy as np
import numpy.typing as npt
from psycopg import AsyncConnection
from psycopg.rows import DictRow

from candidate.config import Filters, Profile
from domain.offer import Offer
from learning.weights import thresholds_for_stage, weights_for_stage
from llm_client import LLMClient
from scoring.decision import combine_score, decide
from scoring.filter import filter_offer
from scoring.judge import judge_offer
from scoring.similarity import embed, knn_score, offer_text, similarity_score, vector_literal

logger = logging.getLogger(__name__)

VERSION = "cascade.v1"
SEND_VERDICTS = frozenset({"great", "worth_it"})


@dataclass(frozen=True)
class ScoringContext:
    """What stays constant for a whole ingest cycle. Embedding the profile or counting ratings
    per offer would repeat the same work once per offer, thousands of times a cycle."""

    llm: LLMClient
    profile: Profile
    filters: Filters
    profile_vector: npt.NDArray[np.float64]
    n_ratings: int


async def score(
    conn: AsyncConnection[DictRow], ctx: ScoringContext, offer_id: UUID, offer: Offer
) -> dict[str, Any]:
    """Run one offer through the cascade and persist the outcome, rejections included."""
    row = _blank_row(offer_id)
    filtered = filter_offer(offer, ctx.filters)
    row["features"] = json.dumps(filtered.features)

    if not filtered.passed:
        row["rejection_stage"] = "filter"
        row["rejection_reason"] = filtered.reason
        return await _persist(conn, row, decision="reject", stage="filter")

    vector = await embed(offer_text(offer))
    await _save_embedding(conn, offer_id, vector)
    similarity = similarity_score(vector, ctx.profile_vector)
    knn = await knn_score(conn, vector)
    row["similarity_score"] = similarity["profile_similarity"]
    row["knn_score"] = knn["knn"] if knn else None

    thresholds = thresholds_for_stage(ctx.n_ratings)
    row["final_score"] = combine_score(
        filtered.features, similarity, knn, weights_for_stage(ctx.n_ratings)
    )
    decision = decide(row["final_score"], thresholds, filtered.features)
    stage = "vector"

    if decision == "ask_llm":
        stage = "judge"
        decision = await _run_judge(ctx, offer, row)
    elif decision == "reject":
        row["rejection_reason"] = f"score {row['final_score']:.3f} < {thresholds['reject']}"

    if decision == "reject":
        row["rejection_stage"] = stage
    return await _persist(conn, row, decision=decision, stage=stage)


async def _run_judge(ctx: ScoringContext, offer: Offer, row: dict[str, Any]) -> str:
    verdict, response = await judge_offer(ctx.llm, offer, ctx.profile, ctx.filters)
    row["cost_usd"] = response.cost_usd
    row["llm_score"] = verdict.score
    row["final_score"] = verdict.score
    row["rationale"] = verdict.reason

    if verdict.manipulation_detected:
        logger.warning("%s/%s: judge flagged manipulation", offer.source, offer.external_id)
        row["rejection_reason"] = "manipulation detected in the posting"
        return "reject"
    if verdict.verdict not in SEND_VERDICTS:
        row["rejection_reason"] = verdict.reason
        return "reject"
    return "send"


def _blank_row(offer_id: UUID) -> dict[str, Any]:
    # rule_score stays null: the filter answers pass/reject with a reason, never a number.
    return {
        "offer_id": offer_id,
        "scoring_version": VERSION,
        "cost_usd": 0.0,
        "features": "{}",
        "rejection_stage": None,
        "rejection_reason": None,
        "rule_score": None,
        "similarity_score": None,
        "knn_score": None,
        "llm_score": None,
        "final_score": None,
        "rationale": None,
    }


async def _save_embedding(
    conn: AsyncConnection[DictRow], offer_id: UUID, vector: npt.NDArray[np.float64]
) -> None:
    await conn.execute(
        "UPDATE offer SET embedding = %s::vector WHERE id = %s", (vector_literal(vector), offer_id)
    )


async def _persist(
    conn: AsyncConnection[DictRow], row: dict[str, Any], decision: str, stage: str
) -> dict[str, Any]:
    await conn.execute(
        """
        INSERT INTO offer_score (
            offer_id, rejection_stage, rejection_reason, rule_score, similarity_score,
            knn_score, llm_score, final_score, rationale, features, scoring_version, cost_usd
        ) VALUES (
            %(offer_id)s, %(rejection_stage)s, %(rejection_reason)s, %(rule_score)s,
            %(similarity_score)s, %(knn_score)s, %(llm_score)s, %(final_score)s,
            %(rationale)s, %(features)s, %(scoring_version)s, %(cost_usd)s
        )
        """,
        row,
    )
    return {
        "decision": decision,
        "stage": stage,
        "score": row["final_score"],
        "cost_usd": row["cost_usd"],
    }
