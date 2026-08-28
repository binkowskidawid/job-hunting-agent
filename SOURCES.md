# Sources

Every source this project reads, why it is allowed to, and what it costs the site. Each entry
must be defensible here before it is switched on in `src/sources/sources.yaml`.

Verified 2026-08-28. `robots.txt` changes without notice — re-check before adding a source,
and when a source starts failing.

## The rules this project holds itself to

1. **`robots.txt` is binding**, including the paths it disallows for reasons that are not
   explained. Where a site offers the same data on an allowed and a disallowed path, the
   allowed one is used even when it is less convenient.
2. **The User-Agent says who is asking** and carries a contact address, so an operator who
   objects can email instead of block: `JobAgent/1.0 (private single-user tool; contact: …)`.
3. **The cheapest request is the one not made.** Discovery costs one request; offer pages are
   filtered down before any of them is fetched, and capped per cycle.
4. **No credential is ever presented.** Nothing here reads content behind a login.
5. **Nothing is republished.** Offers are stored locally and shown to one person, the
   operator. This is a personal tool, not an aggregator.

## justjoin.it — `sitemap_jsonld`, enabled

| | |
| --- | --- |
| Discovery | `https://justjoin.it/sitemaps/active-jobs/part0.xml` |
| Content | schema.org `JobPosting` in `application/ld+json` on `/job-offer/…` |
| Postings listed | **9,955** |
| Fetched per cycle | **at most 200**, 1.0 s apart |
| Cycle interval | 24 h |

**Basis.** `robots.txt` advertises the sitemaps itself, with eight `Sitemap:` directives — a
sitemap exists to be read by machines, and advertising it is an invitation. Offer pages under
`/job-offer/` carry no rule. The JSON-LD block is the format boards publish for Google for
Jobs and other aggregators, so reading it is the use it was put there for.

**What is deliberately not used.** `robots.txt` says `Disallow: /api/`. The board has a JSON
API that would be more convenient and return richer data in fewer requests. It is not used,
and `sitemap_jsonld.py` has no code path to it. `Disallow: /oferty-pracy/*,*` covers the
faceted Polish listing URLs, which are also unused.

**Cost to the site.** One sitemap request per day, plus at most 200 offer pages at one per
second. Before any page is fetched, the URL passes a filter built from the operator's own
criteria; measured against real settings that keeps **483 of 9,955 (4.9%)**, and the 200-page
cap means a first run spreads over several days rather than arriving as a burst.

## nofluffjobs.com — `rss`, not enabled

| | |
| --- | --- |
| Feed | `https://nofluffjobs.com/rss` |
| Entries | **4,371** |
| With a location | **100%** |
| With a salary range | **66%** — the other 34% take the `missing_range` path |
| Cycle interval | 1 h |

**Basis.** A public RSS feed. Publishing one is publishing for machines.

**A trap worth writing down.** `https://nofluffjobs.com/api/rss` serves the same content and
sits under `Disallow: /api/`. The two paths are interchangeable technically and are not
interchangeable ethically. Use `/rss`.

**Also disallowed.** `/posting/` and its localised variants, so individual posting pages are
not fetched. Everything this adapter needs is in the feed.

**Status.** Implemented and tested against a capture of the live feed, switched off in
`sources.yaml` until it is actually wanted. One source is enough to build the cascade against.

## Sources considered and rejected

| Source | Why not |
| --- | --- |
| justjoin.it JSON API | `Disallow: /api/` |
| nofluffjobs.com `/api/rss` | same content as `/rss`, but under `Disallow: /api/` |
| remoteok.com RSS | `HTTP 410 Gone` |
| stackoverflow.com/jobs/feed | `HTTP 404`; the board was retired |
| LinkedIn | terms prohibit automated access; no feed |

## Adding a source

1. Read its `robots.txt` in full and record what is disallowed, not only whether your path is.
2. Prefer, in order: a feed, a sitemap plus structured data, an email alert you subscribed to,
   manual paste. Stop at the first one that works.
3. Write the entry in this file — including what you chose not to use, and why — before
   enabling it in `sources.yaml`.
4. Save a real response as a fixture under `tests/fixtures/` and write a test against it. A
   parser tested only against XML you wrote yourself passes forever and still breaks on
   contact with the site.
