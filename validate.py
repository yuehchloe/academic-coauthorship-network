"""Validate the strict-filtered Semantic Scholar pull.

Run from project root:
    python validate.py

This pulls one query with the strict filters (Economics field-of-study +
top-econ venue allowlist) and reports field coverage plus the venue
distribution. Useful to sanity-check the filters before running the full
six-query pull.
"""

import logging
from collections import Counter

from src.data_loader import DataLoader
from src.venues import TOP_ECON_VENUE_PATTERNS


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    loader = DataLoader(cache_dir="data/cache")
    papers = loader.search_papers(
        "moral hazard",
        year_start=2015,
        year_end=2025,
        limit=500,
        fields_of_study=["Economics"],
        venue_allowlist=TOP_ECON_VENUE_PATTERNS,
    )

    print()
    print("=" * 60)
    print("VALIDATION RESULTS — STRICT FILTERS")
    print("=" * 60)
    print(f"Total papers returned: {len(papers)}")

    if not papers:
        print()
        print("WARNING: zero papers returned. Possible causes:")
        print("  1. fields_of_study=Economics filter too aggressive")
        print("  2. Venue allowlist doesn't match S2's venue strings")
        print("  3. Query genuinely has no top-tier econ-journal results")
        print()
        print("Try removing the venue_allowlist to debug.")
        return

    p = papers[0]
    print()
    print("Sample paper (first result):")
    print(f"  ID:        {p.paper_id}")
    print(f"  Title:     {p.title}")
    print(f"  Year:      {p.year}")
    print(f"  Venue:     {p.venue}")
    print(f"  Citations: {p.citation_count}")
    print(f"  N authors: {len(p.author_ids)}")
    print(f"  Has abstract: {p.abstract is not None}")

    print()
    print("Field coverage across all papers:")
    print(f"  with year:         {sum(1 for x in papers if x.year)}/{len(papers)}")
    print(f"  with venue:        {sum(1 for x in papers if x.venue)}/{len(papers)}")
    print(f"  with abstract:     {sum(1 for x in papers if x.abstract)}/{len(papers)}")
    print(
        f"  with >=2 authors:  {sum(1 for x in papers if x.is_collaborative)}/{len(papers)}"
    )
    print(
        f"  with 0 author IDs: {sum(1 for x in papers if not x.author_ids)}/{len(papers)}"
    )
    n_unique_authors = len({a for x in papers for a in x.author_ids})
    print(f"  unique authors:    {n_unique_authors}")

    print()
    print("Venue distribution (top 15):")
    venue_counts = Counter(p.venue or "<missing>" for p in papers)
    for venue, n in venue_counts.most_common(15):
        print(f"  {n:>4d}  {venue}")

    print()
    print("First 10 paper titles (eyeball check — should all be econ):")
    for x in papers[:10]:
        venue_short = (x.venue or "—")[:30]
        print(f"  {x.year}  {venue_short:30s}  {x.title[:75]}")


if __name__ == "__main__":
    main()
