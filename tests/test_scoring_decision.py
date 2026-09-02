"""Stage 3 of the cascade, offline: the arithmetic that turns three kinds of signal into one
number, and the number into a verdict.

The tech signals are tested as properties (monotone, bounded, zero at zero) rather than
against an exact curve: the shape is a taste decision that may be retuned, the properties
are what combine_score depends on.
"""

from typing import Any

import pytest

from learning.weights import SIGNALS, thresholds_for_stage, weights_for_stage
from scoring.decision import (
    PROFILE_SIM_CEILING,
    PROFILE_SIM_FLOOR,
    combine_score,
    decide,
    tech_bonus_signal,
    tech_penalty_signal,
)

MID_COSINE = (PROFILE_SIM_FLOOR + PROFILE_SIM_CEILING) / 2


def make_features(**overrides: Any) -> dict[str, Any]:
    features: dict[str, Any] = {
        "pluses": [],
        "minuses": [],
        "no_salary_range": False,
        "salary_surplus": 0.0,
    }
    features.update(overrides)
    return features


def make_similarity(profile: float = MID_COSINE, preference: float | None = None) -> dict[str, Any]:
    return {"profile_similarity": profile, "preference_similarity": preference}


class TestProfileSimilarityStretch:
    """768-dimensional cosine occupies roughly [0.58, 0.71] on real offers. Fed in raw, every
    offer shares the same floor and the differences compress into noise."""

    def test_a_cosine_at_the_floor_scores_zero(self) -> None:
        score = combine_score(
            make_features(),
            make_similarity(profile=PROFILE_SIM_FLOOR),
            None,
            {
                **weights_for_stage(0),
                "profile_similarity": 1.0,
                "tech_bonus": 0.0,
                "tech_penalty": 0.0,
                "salary": 0.0,
            },
        )
        assert score == pytest.approx(0.0)

    def test_a_cosine_at_the_ceiling_scores_one(self) -> None:
        score = combine_score(
            make_features(),
            make_similarity(profile=PROFILE_SIM_CEILING),
            None,
            {
                **weights_for_stage(0),
                "profile_similarity": 1.0,
                "tech_bonus": 0.0,
                "tech_penalty": 0.0,
                "salary": 0.0,
            },
        )
        assert score == pytest.approx(1.0)

    @pytest.mark.parametrize("cosine", [-1.0, 0.0, 0.3, PROFILE_SIM_FLOOR - 0.01])
    def test_a_cosine_below_the_floor_clamps_rather_than_going_negative(
        self, cosine: float
    ) -> None:
        """A negative signal would let one weak match drag a strong one below zero."""
        weights = {name: 0.0 for name in SIGNALS} | {"profile_similarity": 1.0}
        assert combine_score(make_features(), make_similarity(profile=cosine), None, weights) == 0.0

    def test_a_cosine_above_the_ceiling_clamps_at_one(self) -> None:
        weights = {name: 0.0 for name in SIGNALS} | {"profile_similarity": 1.0}
        score = combine_score(make_features(), make_similarity(profile=0.99), None, weights)
        assert score == pytest.approx(1.0)


class TestTechSignals:
    def test_no_matches_means_no_bonus(self) -> None:
        assert tech_bonus_signal(0) == 0.0

    def test_no_matches_means_no_penalty(self) -> None:
        """The penalty signal is inverted: weights are positive, so clean means 1.0."""
        assert tech_penalty_signal(0) == 1.0

    @pytest.mark.parametrize("hits", range(0, 8))
    def test_both_signals_stay_inside_the_unit_interval(self, hits: int) -> None:
        """A signal outside [0, 1] breaks the guarantee that the weighted mean is a score."""
        assert 0.0 <= tech_bonus_signal(hits) <= 1.0
        assert 0.0 <= tech_penalty_signal(hits) <= 1.0

    def test_more_pluses_never_score_worse(self) -> None:
        values = [tech_bonus_signal(n) for n in range(0, 8)]
        assert values == sorted(values)

    def test_more_minuses_never_score_better(self) -> None:
        values = [tech_penalty_signal(n) for n in range(0, 8)]
        assert values == sorted(values, reverse=True)

    def test_one_plus_already_moves_the_signal(self) -> None:
        """A first match that scores zero makes the whole signal dead weight below two hits."""
        assert tech_bonus_signal(1) > 0.0

    def test_one_minus_already_costs_something(self) -> None:
        assert tech_penalty_signal(1) < 1.0


class TestRenormalisation:
    """A signal with no value must not be counted as zero: that is a claim about the offer,
    not an absence of one."""

    def test_a_missing_signal_does_not_drag_the_score_down(self) -> None:
        weights = {name: 0.0 for name in SIGNALS} | {"profile_similarity": 0.5, "knn": 0.5}
        with_knn_absent = combine_score(make_features(), make_similarity(), None, weights)
        assert with_knn_absent == pytest.approx(0.5)

    def test_an_available_knn_is_weighed_alongside_the_profile(self) -> None:
        weights = {name: 0.0 for name in SIGNALS} | {"profile_similarity": 0.5, "knn": 0.5}
        score = combine_score(make_features(), make_similarity(), {"knn": 1.0}, weights)
        assert score == pytest.approx(0.75)

    def test_preference_similarity_is_absent_until_centroids_exist(self) -> None:
        """learning/centroids.py is Phase 4, so this signal is None on every offer today."""
        weights = {name: 0.0 for name in SIGNALS} | {
            "profile_similarity": 0.5,
            "preference_similarity": 0.5,
        }
        assert combine_score(make_features(), make_similarity(), None, weights) == pytest.approx(
            0.5
        )

    def test_a_missing_salary_surplus_is_dropped_rather_than_scored_zero(self) -> None:
        """Roughly a third of postings hide their range; scoring them 0.0 rejects them by
        stealth, which is exactly what missing_range: flag decided against."""
        weights = {name: 0.0 for name in SIGNALS} | {"profile_similarity": 0.5, "salary": 0.5}
        priced = make_features(salary_surplus=None)
        del priced["salary_surplus"]
        assert combine_score(priced, make_similarity(), None, weights) == pytest.approx(0.5)

    def test_weights_that_leave_nothing_to_measure_raise(self) -> None:
        """Silently answering 0.0 would look like a rejected offer instead of a broken config."""
        weights = {name: 0.0 for name in SIGNALS} | {"knn": 1.0}
        with pytest.raises(ValueError, match="no signal"):
            combine_score(make_features(), make_similarity(), None, weights)

    @pytest.mark.parametrize("n_ratings", [0, 10, 50])
    def test_every_real_stage_produces_a_score_inside_the_unit_interval(
        self, n_ratings: int
    ) -> None:
        score = combine_score(
            make_features(pluses=["LLM"], minuses=["PHP"], salary_surplus=0.2),
            make_similarity(),
            {"knn": 0.8},
            weights_for_stage(n_ratings),
        )
        assert 0.0 <= score <= 1.0


class TestSalarySignal:
    def test_meeting_the_threshold_exactly_scores_zero(self) -> None:
        weights = {name: 0.0 for name in SIGNALS} | {"salary": 1.0}
        assert (
            combine_score(make_features(salary_surplus=0.0), make_similarity(), None, weights)
            == 0.0
        )

    def test_a_large_surplus_saturates_instead_of_dominating(self) -> None:
        """salary_surplus is unbounded above: 300% over the floor must not outweigh fit."""
        weights = {name: 0.0 for name in SIGNALS} | {"salary": 1.0}
        assert (
            combine_score(make_features(salary_surplus=3.0), make_similarity(), None, weights)
            == 1.0
        )


class TestDecide:
    THRESHOLDS = thresholds_for_stage(0)

    def test_a_score_on_the_send_threshold_sends(self) -> None:
        assert decide(self.THRESHOLDS["send"], self.THRESHOLDS, make_features()) == "send"

    def test_a_score_on_the_reject_threshold_is_not_rejected(self) -> None:
        """The gap is inclusive at the bottom: a false negative disappears without a trace."""
        assert decide(self.THRESHOLDS["reject"], self.THRESHOLDS, make_features()) == "ask_llm"

    def test_a_score_below_the_reject_threshold_is_rejected(self) -> None:
        assert (
            decide(self.THRESHOLDS["reject"] - 0.01, self.THRESHOLDS, make_features()) == "reject"
        )

    def test_the_gap_between_thresholds_goes_to_the_judge(self) -> None:
        middle = (self.THRESHOLDS["send"] + self.THRESHOLDS["reject"]) / 2
        assert decide(middle, self.THRESHOLDS, make_features()) == "ask_llm"

    def test_an_offer_with_no_salary_range_is_never_sent_unjudged(self) -> None:
        """A Discord card without the number is not worth the notification."""
        features = make_features(no_salary_range=True)
        assert decide(1.0, self.THRESHOLDS, features) == "ask_llm"

    def test_an_offer_with_no_exchange_rate_is_never_sent_unjudged(self) -> None:
        """The filter deliberately passed it, but the floor was never actually compared."""
        features = make_features(fx_unavailable="EUR")
        assert decide(1.0, self.THRESHOLDS, features) == "ask_llm"

    def test_an_unpriced_offer_below_the_reject_threshold_is_still_rejected(self) -> None:
        """The override withholds a send; it does not buy a judge call for a weak offer."""
        features = make_features(no_salary_range=True)
        assert decide(0.0, self.THRESHOLDS, features) == "reject"
