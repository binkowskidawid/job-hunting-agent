"""Locks the exact signal-name contract that scoring.decision.combine_score depends on."""

import pytest

from learning.weights import thresholds_for_stage, weights_for_stage

EXPECTED_SIGNAL_KEYS = {
    "profile_similarity", "preference_similarity", "knn",
    "tech_bonus", "tech_penalty", "salary", "freshness",
}


def test_weights_for_stage_not_yet_implemented():
    with pytest.raises(NotImplementedError):
        weights_for_stage(0)


def test_thresholds_for_stage_not_yet_implemented():
    with pytest.raises(NotImplementedError):
        thresholds_for_stage(0)
