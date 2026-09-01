"""The cold-start invariants. These are properties of every stage, so they are tested
across stages rather than one case per stage."""

import pytest

from learning.weights import SIGNALS, thresholds_for_stage, weights_for_stage

# One below, one on, and one above each boundary, plus a far-future count.
RATING_COUNTS = [0, 1, 9, 10, 11, 49, 50, 51, 500]


@pytest.mark.parametrize("n_ratings", RATING_COUNTS)
def test_every_stage_weighs_exactly_the_known_signals(n_ratings: int) -> None:
    """A typo in a key drops that signal from combine_score without redistributing it."""
    assert set(weights_for_stage(n_ratings)) == set(SIGNALS)


@pytest.mark.parametrize("n_ratings", RATING_COUNTS)
def test_every_stage_sums_to_one(n_ratings: int) -> None:
    """Otherwise final_score values from two stages are not comparable."""
    assert sum(weights_for_stage(n_ratings).values()) == pytest.approx(1.0)


@pytest.mark.parametrize("n_ratings", RATING_COUNTS)
def test_no_weight_is_negative(n_ratings: int) -> None:
    assert all(weight >= 0.0 for weight in weights_for_stage(n_ratings).values())


def test_cold_start_ignores_the_signals_it_cannot_compute() -> None:
    """A weight on an absent signal silently redistributes itself across the rest."""
    cold = weights_for_stage(0)
    assert cold["preference_similarity"] == 0.0
    assert cold["knn"] == 0.0


def test_freshness_stays_at_zero_until_something_computes_it() -> None:
    """No module computes it; the key is kept so combine_score can read it later."""
    assert all(weights_for_stage(n)["freshness"] == 0.0 for n in RATING_COUNTS)


def test_the_profile_keeps_a_residual_weight_forever() -> None:
    """A system trained only on its own feedback drifts toward what it already shows."""
    assert weights_for_stage(10_000)["profile_similarity"] > 0.0


def test_learned_signals_grow_as_the_profile_signal_recedes() -> None:
    cold, warming, warm = (weights_for_stage(n) for n in (0, 10, 50))
    assert cold["profile_similarity"] > warming["profile_similarity"] > warm["profile_similarity"]
    assert cold["knn"] < warming["knn"] < warm["knn"]


@pytest.mark.parametrize("n_ratings", RATING_COUNTS)
def test_send_always_sits_above_reject(n_ratings: int) -> None:
    """Inverted thresholds would empty the uncertain zone and skip the judge entirely."""
    thresholds = thresholds_for_stage(n_ratings)
    assert thresholds["send"] > thresholds["reject"]


def test_the_uncertain_zone_only_narrows_as_the_system_learns() -> None:
    """A false negative disappears with no trace, so the zone starts wide."""
    gaps = [
        thresholds_for_stage(n)["send"] - thresholds_for_stage(n)["reject"] for n in (0, 10, 50)
    ]
    assert gaps == sorted(gaps, reverse=True)
