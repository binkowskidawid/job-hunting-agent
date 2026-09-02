"""Combines filter features + similarity + kNN into one score, then decides:
send / reject / ask the LLM judge."""

from typing import Any

# Measured 2026-09-01: on real offers the cosine spans 0.58 (CNC lathe operator) to 0.71.
# Raw, the signal is a constant plus noise.
PROFILE_SIM_FLOOR = 0.55
PROFILE_SIM_CEILING = 0.75
SALARY_SURPLUS_CAP = 0.5
TECH_SATURATION_HITS = 4


def combine_score(
    features: dict[str, Any],
    similarity: dict[str, Any],
    knn: dict[str, Any] | None,
    weights: dict[str, Any],
) -> float:
    signals: dict[str, float | None] = {
        "profile_similarity": _stretch(similarity["profile_similarity"]),
        "preference_similarity": similarity["preference_similarity"],
        "knn": knn["knn"] if knn else None,
        "tech_bonus": tech_bonus_signal(len(features["pluses"])),
        "tech_penalty": tech_penalty_signal(len(features["minuses"])),
        "salary": _salary_signal(features.get("salary_surplus")),
        "freshness": None,
    }
    return _weighted_mean(signals, weights)


def tech_bonus_signal(hits: int) -> float:
    """Credit for `hits` matches against `technologies.big_plus`.

    Monotone non-decreasing, bounded by [0, 1], 0.0 at zero hits.
    """
    return min(hits / TECH_SATURATION_HITS, 1.0)


def tech_penalty_signal(hits: int) -> float:
    """Cost of `hits` matches against `technologies.minus`, inverted because the weight is
    positive: monotone non-increasing, bounded by [0, 1], 1.0 at zero hits.
    """
    return 1.0 - min(hits / TECH_SATURATION_HITS, 1.0)


def decide(score: float, thresholds: dict[str, Any], features: dict[str, Any]) -> str:
    """Returns 'send' | 'reject' | 'ask_llm'."""
    if score < thresholds["reject"]:
        return "reject"
    if score >= thresholds["send"] and not _unpriced(features):
        return "send"
    return "ask_llm"


def _unpriced(features: dict[str, Any]) -> bool:
    return bool(features.get("no_salary_range")) or "fx_unavailable" in features


def _stretch(cosine: float) -> float:
    return min(
        max((cosine - PROFILE_SIM_FLOOR) / (PROFILE_SIM_CEILING - PROFILE_SIM_FLOOR), 0.0), 1.0
    )


def _salary_signal(surplus: float | None) -> float | None:
    if surplus is None:
        return None
    return min(max(surplus / SALARY_SURPLUS_CAP, 0.0), 1.0)


def _weighted_mean(signals: dict[str, float | None], weights: dict[str, Any]) -> float:
    """Renormalises over the signals that exist: absence is not a claim about the offer."""
    available = [(weights[name], value) for name, value in signals.items() if value is not None]
    total_weight = sum(weight for weight, _ in available)
    if total_weight == 0.0:
        raise ValueError("no signal with a non-zero weight is available for this offer")
    return float(sum(weight * value for weight, value in available) / total_weight)
