"""The hand-edited config boundary: a typo here must fail at load, not at decision time."""

from pathlib import Path

import pytest

from candidate.config import (
    FILTERS_PATH,
    PROFILE_PATH,
    Level,
    load_filters,
    load_profile,
)

VALID_PROFILE = """
target_roles: [Senior Backend Engineer]
years_experience: 8
competencies:
  - name: Python
    level: expert
    years: 6
    context: Async services under load.
  - name: Kubernetes
    level: basic
differentiators: [Backend and DevOps in one person]
"""


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_profile_loads_and_defaults_the_optional_fields(tmp_path: Path) -> None:
    profile = load_profile(_write(tmp_path, "profile.yaml", VALID_PROFILE))

    assert profile.years_experience == 8
    assert profile.competencies[0].level is Level.EXPERT
    assert profile.competencies[1].years is None
    assert profile.domains == []


def test_profile_rejects_a_level_outside_the_enum(tmp_path: Path) -> None:
    body = VALID_PROFILE.replace("level: expert", "level: wizard")

    with pytest.raises(ValueError, match="wizard"):
        load_profile(_write(tmp_path, "profile.yaml", body))


def test_filters_reject_a_work_mode_the_adapters_never_produce(tmp_path: Path) -> None:
    # `remot` would otherwise match nothing and silently reject every offer.
    body = "work_mode:\n  accepted: [remot]\n"

    with pytest.raises(ValueError, match="remot"):
        load_filters(_write(tmp_path, "filters.yaml", body))


def test_missing_file_points_at_the_example(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"profile\.example\.yaml"):
        load_profile(tmp_path / "profile.yaml")


def test_as_text_carries_the_context_not_just_the_skill_name(tmp_path: Path) -> None:
    text = load_profile(_write(tmp_path, "profile.yaml", VALID_PROFILE)).as_text()

    assert "Async services under load." in text
    assert "Python (expert, 6 years)" in text
    assert "Kubernetes (basic)" in text
    assert "Backend and DevOps in one person" in text


def test_the_shipped_examples_still_validate() -> None:
    """A template that no longer parses is documentation that lies on a fresh clone."""
    load_profile(PROFILE_PATH.with_suffix(".example.yaml"))
    load_filters(FILTERS_PATH.with_suffix(".example.yaml"))
