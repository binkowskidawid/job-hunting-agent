"""Golden-set runner for the deterministic parts (CV extraction, filter rules) —
tests properties, not exact values, because temperature 0 isn't determinism."""

from typing import Any


def check(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError


def main(case_dir: str) -> None:
    raise NotImplementedError
