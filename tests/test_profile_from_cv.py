"""Verifies the CVCompetencies schema carries provenance per competency."""

from profile.from_cv import Competency, CVCompetencies


def test_competency_requires_confidence_and_source_quote() -> None:
    c = Competency(
        name="React",
        level="expert",
        years=3.0,
        context="Led the CRA migration",
        confidence=0.9,
        source_quote="led the migration off CRA",
    )
    assert 0.0 <= c.confidence <= 1.0
    assert c.source_quote


def test_cv_competencies_construction() -> None:
    profile = CVCompetencies(
        target_roles=["Full-Stack"],
        years_experience=5.0,
        competencies=[],
        domains=[],
        languages=[],
        differentiators=[],
    )
    assert profile.years_experience == 5.0
