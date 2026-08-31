"""Stage 1 of the cascade, offline: no network, no database, no model.

The thresholds below are synthetic. They must not mirror the gitignored `filters.yaml`, whose
numbers are personal and would rot into this file the first time they change.
"""

from typing import Any

import pytest
from pydantic import HttpUrl

from candidate.config import Filters
from domain.offer import ContractType, Offer, WorkMode
from scoring.filter import WORKING_HOURS_PER_MONTH, _salary_threshold, filter_offer

MONTHLY_B2B_FLOOR = 10_000
MONTHLY_EMPLOYMENT_FLOOR = 12_000
HOURLY_B2B_FLOOR = 80
HOURLY_FLOOR_AS_MONTHLY = HOURLY_B2B_FLOOR * WORKING_HOURS_PER_MONTH
EUR_RATE = {"EUR": 4.33}

FILTERS = Filters.model_validate(
    {
        "salary": {
            "min_b2b_month": MONTHLY_B2B_FLOOR,
            "min_employment_month": MONTHLY_EMPLOYMENT_FLOOR,
            "min_hourly_b2b": HOURLY_B2B_FLOOR,
            "missing_range": "flag",
        },
        "work_mode": {"accepted": ["remote"], "hybrid_allowed_cities": []},
        "contract_type": {"accepted": ["b2b", "employment_contract"], "preferred": "b2b"},
        "level": {
            "accepted": ["mid", "senior", "regular"],
            "reject_outright": ["junior", "intern", "trainee", "praktykant", "stażysta"],
        },
        "stop_words": {"title": [".NET", "Java", "Salesforce", "QA", "Tester"], "description": []},
        "technologies": {
            "required_at_least_one": [
                "TypeScript",
                "JavaScript",
                "React",
                "Next.js",
                "Node.js",
                "Python",
            ],
            "big_plus": ["Next.js", "LLM", "PostgreSQL", "Docker"],
            "minus": ["Angular", "Vue", "PHP"],
            "veto": [".NET", "C#", "Java", "Spring", "Salesforce"],
        },
    }
)


def make_offer(**overrides: Any) -> Offer:
    fields: dict[str, Any] = {
        "source": "test",
        "external_id": "1",
        "url": HttpUrl("https://example.test/1"),
        "title": "Senior React Developer",
        "description": "React and TypeScript, remote.",
        "salary_min": 15_000,
        "salary_max": 20_000,
        "currency": "PLN",
        "period": "month",
        "work_mode": WorkMode.REMOTE,
        "contract_type": ContractType.B2B,
    }
    return Offer(**(fields | overrides))


def test_javascript_is_not_java() -> None:
    result = filter_offer(make_offer(title="Senior JavaScript Developer"), FILTERS)
    assert result.passed, result.reason


def test_dotnet_is_caught_inside_asp_net() -> None:
    result = filter_offer(make_offer(title="ASP.NET Core Developer"), FILTERS)
    assert not result.passed
    assert ".NET" in (result.reason or "")


def test_internal_tools_is_not_an_internship() -> None:
    result = filter_offer(make_offer(title="React Developer, Internal Tools"), FILTERS)
    assert result.passed, result.reason


def test_junior_is_rejected_from_the_title_alone() -> None:
    offer = make_offer(title="Junior React Developer")
    assert offer.level is None
    result = filter_offer(offer, FILTERS)
    assert not result.passed
    assert result.reason == "level: junior"


def test_offer_outside_the_stack_is_rejected() -> None:
    offer = make_offer(title="Senior Golang Developer", description="Go, Kubernetes, gRPC.")
    result = filter_offer(offer, FILTERS)
    assert not result.passed
    assert result.reason == "no core technology"


def test_unknown_work_mode_passes() -> None:
    result = filter_offer(make_offer(work_mode=WorkMode.UNKNOWN), FILTERS)
    assert result.passed, result.reason


def test_features_come_from_text_when_the_source_ships_no_tags() -> None:
    offer = make_offer(
        title="Senior Next.js Developer",
        description="Next.js, PostgreSQL and Docker. Some legacy Angular to retire.",
    )
    assert offer.technologies == []
    result = filter_offer(offer, FILTERS)
    assert result.passed, result.reason
    assert result.features["core_hits"] == ["Next.js"]
    assert result.features["pluses"] == ["Docker", "Next.js", "PostgreSQL"]
    assert result.features["minuses"] == ["Angular"]


@pytest.mark.parametrize(
    ("period", "salary_max", "passes"),
    [
        ("hour", 80, True),
        ("hour", 79, False),
        ("day", 500, True),
        ("day", 400, False),
        ("week", 2400, True),
        ("week", 2000, False),
        ("month", 10_000, True),
        ("month", 9_999, False),
        ("year", 150_000, True),
        ("year", 100_000, False),
        (None, 10_000, True),
        (None, 9_999, False),
    ],
)
def test_every_period_is_normalised_to_pln_per_month(
    period: str | None, salary_max: int, passes: bool
) -> None:
    offer = make_offer(period=period, salary_min=None, salary_max=salary_max)
    result = filter_offer(offer, FILTERS)
    assert result.passed is passes, result.reason


def test_unknown_contract_type_is_still_compared() -> None:
    fields: dict[str, Any] = {"contract_type": ContractType.UNKNOWN, "salary_min": None}
    assert filter_offer(make_offer(salary_max=MONTHLY_B2B_FLOOR, **fields), FILTERS).passed
    assert not filter_offer(make_offer(salary_max=9_000, **fields), FILTERS).passed


def test_employment_contract_has_its_own_floor() -> None:
    fields: dict[str, Any] = {
        "contract_type": ContractType.EMPLOYMENT_CONTRACT,
        "salary_min": None,
    }
    assert filter_offer(make_offer(salary_max=MONTHLY_EMPLOYMENT_FLOOR, **fields), FILTERS).passed
    assert not filter_offer(make_offer(salary_max=11_000, **fields), FILTERS).passed


def test_compares_max_not_min() -> None:
    result = filter_offer(make_offer(salary_min=5_000, salary_max=20_000), FILTERS)
    assert result.passed, result.reason


def test_missing_range_is_flagged_not_rejected() -> None:
    result = filter_offer(make_offer(salary_min=None, salary_max=None), FILTERS)
    assert result.passed, result.reason
    assert result.features["no_salary_range"] is True
    assert "salary_pln_month" not in result.features


def test_foreign_currency_is_converted() -> None:
    offer = make_offer(currency="EUR", salary_min=None, salary_max=5_000)
    result = filter_offer(offer, FILTERS, EUR_RATE)
    assert result.passed, result.reason
    assert result.features["salary_pln_month"] == 21_650


def test_foreign_currency_below_the_floor_is_rejected() -> None:
    offer = make_offer(currency="EUR", salary_min=None, salary_max=2_000)
    result = filter_offer(offer, FILTERS, EUR_RATE)
    assert not result.passed
    assert result.features["salary_pln_month"] == 8_660


def test_missing_rate_flags_instead_of_rejecting() -> None:
    offer = make_offer(currency="EUR", salary_min=None, salary_max=2_000)
    result = filter_offer(offer, FILTERS)
    assert result.passed, result.reason
    assert result.features["fx_unavailable"] == "EUR"
    assert "salary_pln_month" not in result.features


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"period": "hour"}, HOURLY_FLOOR_AS_MONTHLY),
        (
            {"period": "month", "contract_type": ContractType.EMPLOYMENT_CONTRACT},
            MONTHLY_EMPLOYMENT_FLOOR,
        ),
        ({"period": "month", "contract_type": ContractType.B2B}, MONTHLY_B2B_FLOOR),
        ({"period": None, "contract_type": ContractType.UNKNOWN}, MONTHLY_B2B_FLOOR),
    ],
)
def test_salary_threshold_lands_in_the_monthly_space(
    overrides: dict[str, Any], expected: int
) -> None:
    assert _salary_threshold(make_offer(**overrides), FILTERS) == expected


def test_no_floor_configured_means_no_comparison() -> None:
    assert not _salary_threshold(make_offer(), Filters())


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "Senior Java Developer"},
        {"title": "QA Engineer"},
        {"title": "Junior React Developer"},
        {"title": "Senior Golang Developer", "description": "Go and Kubernetes."},
        {"work_mode": WorkMode.ONSITE},
        {"contract_type": ContractType.MANDATE_CONTRACT},
        {"salary_min": None, "salary_max": 9_000},
    ],
)
def test_every_rejection_carries_a_reason(overrides: dict[str, Any]) -> None:
    result = filter_offer(make_offer(**overrides), FILTERS)
    assert not result.passed
    assert result.reason
