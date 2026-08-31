"""Rule-based filter, the free and deterministic first stage of the scoring cascade.
Every rejection must carry a reason."""

import re
from dataclasses import dataclass
from typing import Any

from candidate.config import Filters
from domain.offer import ContractType, Offer, WorkMode

WORKING_HOURS_PER_MONTH = 168
WORKING_DAYS_PER_MONTH = 21
WEEKS_PER_MONTH = 4.33
MONTHS_PER_YEAR = 12

_PERIODS_PER_MONTH = {
    "hour": float(WORKING_HOURS_PER_MONTH),
    "day": float(WORKING_DAYS_PER_MONTH),
    "week": WEEKS_PER_MONTH,
    "month": 1.0,
    "year": 1 / MONTHS_PER_YEAR,
}
_UNKNOWN_PERIOD_ASSUMED_MONTHLY = 1.0


@dataclass
class FilterResult:
    passed: bool
    reason: str | None
    features: dict[str, Any]


def filter_offer(offer: Offer, cfg: Filters, rates: dict[str, float] | None = None) -> FilterResult:
    """`rates` is passed in rather than fetched here, so this stage stays pure and testable
    without a network or a database. `None` is a valid production state, not an error.
    """
    title = offer.title.lower()
    description = offer.description.lower()
    tags = {t.lower() for t in offer.technologies}
    features: dict[str, Any] = {}

    if reason := _hard_reject(offer, cfg, title, description, tags):
        return FilterResult(False, reason, features)

    reason, salary_features = _salary_check(offer, cfg, rates)
    features |= salary_features
    if reason:
        return FilterResult(False, reason, features)

    features["core_hits"] = _hits(cfg.technologies.required_at_least_one, tags, title, description)
    if not features["core_hits"]:
        return FilterResult(False, "no core technology", features)

    features["pluses"] = _hits(cfg.technologies.big_plus, tags, title, description)
    features["minuses"] = _hits(cfg.technologies.minus, tags, title, description)
    features["work_mode"] = offer.work_mode.value
    features["description_length"] = len(offer.description)
    return FilterResult(True, None, features)


def _hard_reject(
    offer: Offer, cfg: Filters, title: str, description: str, tags: set[str]
) -> str | None:
    for word in cfg.stop_words.title:
        if _mentions(word, title):
            return f"stop word in title: {word}"

    for word in cfg.stop_words.description:
        if _mentions(word, description):
            return f"stop word in description: {word}"

    for word in cfg.technologies.veto:
        if word.lower() in tags or _mentions(word, title):
            return f"vetoed technology: {word}"

    for word in cfg.level.reject_outright:
        if _mentions(word, f"{offer.level or ''} {title}"):
            return f"level: {word}"

    if offer.work_mode is not WorkMode.UNKNOWN and offer.work_mode not in cfg.work_mode.accepted:
        return f"work mode: {offer.work_mode.value}"
    if offer.work_mode is WorkMode.HYBRID and cfg.work_mode.hybrid_allowed_cities:
        reachable = {c.lower() for c in cfg.work_mode.hybrid_allowed_cities}
        if offer.locations and not any(loc.lower() in reachable for loc in offer.locations):
            return f"hybrid outside reach: {', '.join(offer.locations)}"

    if (
        offer.contract_type is not ContractType.UNKNOWN
        and offer.contract_type not in cfg.contract_type.accepted
    ):
        return f"contract type: {offer.contract_type.value}"

    return None


def _salary_check(
    offer: Offer, cfg: Filters, rates: dict[str, float] | None
) -> tuple[str | None, dict[str, Any]]:
    features: dict[str, Any] = {"period": offer.period, "currency": offer.currency}

    if offer.salary_max is None:
        features["no_salary_range"] = True
        if cfg.salary.missing_range == "reject":
            return "no salary range", features
        return None, features

    features["no_salary_range"] = False
    rate = _rate_to_pln(offer.currency, rates)
    if rate is None:
        features["fx_unavailable"] = offer.currency
        return None, features

    periods = _PERIODS_PER_MONTH.get(offer.period or "", _UNKNOWN_PERIOD_ASSUMED_MONTHLY)
    monthly = offer.salary_max * periods * rate
    features["salary_pln_month"] = round(monthly)

    threshold = _salary_threshold(offer, cfg)
    if threshold:
        if monthly < threshold:
            return f"{round(monthly)} PLN/month < threshold {threshold}", features
        features["salary_surplus"] = round((monthly - threshold) / threshold, 3)
    return None, features


def _salary_threshold(offer: Offer, cfg: Filters) -> int:
    """The floor this offer must clear, in PLN per month.

    `filters.yaml` holds separate floors rather than one number with conversions: the hourly
    rule is not derived from the monthly one, so an offer quoted per hour is held to the
    hourly floor, scaled into the shared monthly space.

    Falsy means "do not compare".
    """
    if offer.contract_type is ContractType.EMPLOYMENT_CONTRACT:
        return cfg.salary.min_employment_month
    if offer.period == "hour":
        return cfg.salary.min_hourly_b2b * WORKING_HOURS_PER_MONTH
    return cfg.salary.min_b2b_month


def _rate_to_pln(currency: str, rates: dict[str, float] | None) -> float | None:
    if currency.upper() == "PLN":
        return 1.0
    return None if rates is None else rates.get(currency.upper())


def _mentions(needle: str, haystack_lower: str) -> bool:
    """`Java` must not match `JavaScript`, but `.NET` must match `ASP.NET`. The boundary is on
    the right only: a left-hand one breaks `.NET`, whose preceding character is a word character.
    """
    return re.search(rf"{re.escape(needle.lower())}(?![a-z0-9+#])", haystack_lower) is not None


def _hits(words: list[str], tags: set[str], *texts: str) -> list[str]:
    return sorted(
        w for w in words if w.lower() in tags or any(_mentions(w, text) for text in texts)
    )
