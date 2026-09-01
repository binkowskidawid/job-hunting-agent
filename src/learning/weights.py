"""Cold start: signal weights and decision thresholds shift as ratings accumulate."""

from typing import Any

SIGNALS = (
    "profile_similarity",
    "preference_similarity",
    "knn",
    "tech_bonus",
    "tech_penalty",
    "salary",
    "freshness",
)

_KNN_AVAILABLE_AT = 10
_CENTROIDS_MEANINGFUL_AT = 50


def weights_for_stage(n_ratings: int) -> dict[str, Any]:
    """How much each signal counts. Every stage covers SIGNALS exactly and sums to 1.0.

    `preference_similarity` and `knn` weigh 0 until there is data behind them.
    `profile_similarity` never reaches 0: a system trained only on its own feedback drifts
    toward what it already shows you. `freshness` weighs 0 everywhere because no module
    computes it yet.
    """
    if n_ratings < _KNN_AVAILABLE_AT:
        return {
            "profile_similarity": 0.55,
            "preference_similarity": 0.0,
            "knn": 0.0,
            "tech_bonus": 0.25,
            "tech_penalty": 0.15,
            "salary": 0.05,
            "freshness": 0.0,
        }
    if n_ratings < _CENTROIDS_MEANINGFUL_AT:
        return {
            "profile_similarity": 0.30,
            "preference_similarity": 0.15,
            "knn": 0.30,
            "tech_bonus": 0.13,
            "tech_penalty": 0.07,
            "salary": 0.05,
            "freshness": 0.0,
        }
    return {
        "profile_similarity": 0.15,
        "preference_similarity": 0.25,
        "knn": 0.40,
        "tech_bonus": 0.10,
        "tech_penalty": 0.05,
        "salary": 0.05,
        "freshness": 0.0,
    }


def thresholds_for_stage(n_ratings: int) -> dict[str, Any]:
    """Send and reject cutoffs; everything between them goes to the paid judge.

    A false positive costs one judge call and gets caught; a false negative disappears with
    no trace, so the gap starts wide and narrows only as signals become available. These are
    starting points, not a calibration: see learning/calibration.py, out of scope for v0.1.
    """
    if n_ratings < _KNN_AVAILABLE_AT:
        return {"send": 0.75, "reject": 0.35}
    if n_ratings < _CENTROIDS_MEANINGFUL_AT:
        return {"send": 0.72, "reject": 0.42}
    return {"send": 0.70, "reject": 0.48}
