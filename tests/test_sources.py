"""Adapter tests, run against responses captured from the live sites on 2026-08-28.

A parser tested only against XML written by its own author passes forever and still breaks on
contact with a real feed. Everything here parses bytes those sites actually served.
"""

from pathlib import Path

import httpx
import pytest

from domain.offer import Offer, WorkMode
from sources.config import build_adapters, load_sources
from sources.rss import RssAdapter
from sources.sitemap_jsonld import SitemapJsonLdAdapter, _locs, _parse_xml

FIXTURES = Path(__file__).parent / "fixtures"

# A tiny "billion laughs" document. Four nesting levels is already 30,000 characters; nine is
# gigabytes, which is the whole attack.
BILLION_LAUGHS = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
]>
<rss><channel><item><title>&lol2;</title></channel></rss>"""


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- RSS ---------------------------------------------------------------------------------


@pytest.fixture
def rss_offers() -> list[Offer]:
    return RssAdapter("nofluffjobs", "https://example.test/rss").parse(_fixture("nofluffjobs.rss"))


def test_rss_parses_every_entry_in_a_real_feed(rss_offers: list[Offer]) -> None:
    assert len(rss_offers) == 6
    assert all(o.source == "nofluffjobs" for o in rss_offers)
    assert all(str(o.url).startswith("https://nofluffjobs.com/job/") for o in rss_offers)


def test_rss_splits_company_out_of_the_title(rss_offers: list[Offer]) -> None:
    offer = rss_offers[0]

    assert offer.title == "Junior Asset Analyst"
    assert offer.company == "Harvey Nash Technology"


def test_rss_reads_the_worded_salary_range(rss_offers: list[Offer]) -> None:
    # "from 50 to 60 PLN per hour" — the form these boards use. A parser that only knows
    # "50 - 60 PLN" matches nothing here and reports every offer as having no range.
    offer = rss_offers[0]

    assert (offer.salary_min, offer.salary_max) == (50, 60)
    assert (offer.currency, offer.period) == ("PLN", "hour")


def test_rss_leaves_a_missing_range_unset_rather_than_zero(rss_offers: list[Offer]) -> None:
    without = [o for o in rss_offers if o.salary_min is None]

    assert without, "the fixture is meant to include offers with no salary line"
    assert all(o.salary_max is None for o in without)


def test_rss_undoes_the_double_escaping_real_feeds_ship(rss_offers: list[Offer]) -> None:
    # The feed carries `&amp;amp;`; the XML parser resolves one level, leaving `&amp;` to
    # reach the embedding and the Discord card unless it is unescaped again.
    titles = [o.title for o in rss_offers]

    assert any("Logistics AI & ML" in t for t in titles)
    assert not any("&amp;" in t for t in titles)


def test_rss_detects_remote_from_the_text(rss_offers: list[Offer]) -> None:
    assert any(o.work_mode is WorkMode.REMOTE for o in rss_offers)


def test_rss_refuses_an_entity_expansion_bomb() -> None:
    offers = RssAdapter("hostile", "https://example.test/rss").parse(BILLION_LAUGHS)

    assert offers == []


def test_rss_survives_a_feed_that_is_not_xml() -> None:
    assert RssAdapter("broken", "https://example.test/rss").parse("<html>nope") == []


# --- Sitemap + JSON-LD -------------------------------------------------------------------


def test_sitemap_yields_offer_urls() -> None:
    root = _parse_xml(_fixture("justjoin_sitemap.xml"), "test")
    assert root is not None

    urls = _locs(root, "url")

    assert len(urls) == 8
    assert all(u.startswith("https://justjoin.it/job-offer/") for u in urls)


def test_jsonld_maps_a_real_posting_onto_the_offer_schema() -> None:
    adapter = SitemapJsonLdAdapter("justjoin", "https://example.test/sitemap.xml")
    url = "https://justjoin.it/job-offer/ingenious-build-senior-php-developer-warszawa-php"

    offer = adapter.parse_offer(_fixture("justjoin_offer.html"), url)

    assert offer is not None
    assert offer.title == "Senior PHP Developer"
    assert offer.company == "Ingenious.Build"
    assert (offer.salary_min, offer.salary_max) == (19000, 26000)
    assert (offer.currency, offer.period) == ("PLN", "month")
    assert offer.work_mode is WorkMode.REMOTE  # jobLocationType: TELECOMMUTE
    assert offer.locations == ["Warszawa"]
    assert offer.external_id == "ingenious-build-senior-php-developer-warszawa-php"


def test_jsonld_returns_none_when_the_page_carries_no_posting() -> None:
    adapter = SitemapJsonLdAdapter("justjoin", "https://example.test/sitemap.xml")

    assert adapter.parse_offer("<html><body>404</body></html>", "https://x.test/a") is None


async def test_should_fetch_gates_page_requests() -> None:
    """The whole point of the gate: pages not wanted are never requested at all."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path.endswith("sitemap.xml"):
            return httpx.Response(200, text=_fixture("justjoin_sitemap.xml"))
        return httpx.Response(200, text=_fixture("justjoin_offer.html"))

    adapter = SitemapJsonLdAdapter(
        "justjoin",
        "https://justjoin.it/sitemap.xml",
        should_fetch=lambda url: "php" in url,
        delay_s=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        urls = await adapter._discover(http)
    wanted = [u for u in urls if adapter.should_fetch(u)]

    assert len(urls) == 8
    assert 0 < len(wanted) < len(urls)
    assert requested == ["https://justjoin.it/sitemap.xml"]


# --- Configuration -----------------------------------------------------------------------


def test_the_shipped_sources_file_still_builds_its_adapters() -> None:
    sources = load_sources()
    adapters = build_adapters(sources)

    assert {s.name for s in sources.sources} >= {"justjoin", "nofluffjobs"}
    # Only enabled entries are instantiated, and every entry declares why it is allowed.
    assert [a.name for a in adapters] == [s.name for s in sources.sources if s.enabled]
    assert all(s.basis_note for s in sources.sources)


def test_an_entry_missing_its_mechanism_argument_is_skipped_not_crashed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(
        "sources:\n  - name: broken\n    type: rss\n    basis_note: public feed\n",  # no url
        encoding="utf-8",
    )

    assert build_adapters(load_sources(path)) == []
