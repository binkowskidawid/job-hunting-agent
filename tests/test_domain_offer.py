"""Verifies the Offer schema accepts its core fields."""

from pydantic import HttpUrl

from domain.offer import ContractType, Offer, WorkMode


def test_offer_minimal_construction() -> None:
    offer = Offer(
        source="manual",
        external_id="1",
        url=HttpUrl("https://example.com/job/1"),
        title="Senior Full-Stack Engineer",
    )
    assert offer.contract_type == ContractType.UNKNOWN
    assert offer.work_mode == WorkMode.UNKNOWN
    assert offer.locations == []


def test_offer_multilocation_is_a_list() -> None:
    offer = Offer(
        source="manual",
        external_id="1",
        url=HttpUrl("https://example.com/job/1"),
        title="x",
        locations=["Warsaw", "Wrocław"],
    )
    assert offer.locations == ["Warsaw", "Wrocław"]
