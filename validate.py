"""Validate the citation-expansion path against ONE seed author.

Run from project root:
    python validate.py

This resolves one seed author, fetches their papers, expands a few
citations, and reports the numbers. Useful to confirm the new endpoints
work before committing to the ~30-minute full pull.

If this validates cleanly, run:
    python scripts/pull_corpus.py
"""

import logging

from src.data_loader import DataLoader
from src.venues import venue_matches


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    loader = DataLoader(cache_dir="data/cache")

    # Use Bergemann as the test seed — he's prolific in info-econ and
    # publishes in venues squarely on our allowlist (Econometrica, AER,
    # JET). Good signal-to-noise for validation.
    test_author = "Dirk Bergemann"
    print(f"\n[1/3] Resolving author: {test_author}")
    author_id = loader.resolve_author_by_name(test_author)
    if author_id is None:
        print("  FAIL: could not resolve author")
        return
    print(f"  Resolved to authorId: {author_id}")

    print(f"\n[2/3] Fetching papers (2015-2025)")
    papers = loader.fetch_author_papers(
        author_id,
        year_start=2015,
        year_end=2025,
        limit=200,
    )
    print(f"  Got {len(papers)} papers in window")

    in_venue = [p for p in papers if venue_matches(p.venue)]
    print(f"  Of which in econ venue allowlist: {len(in_venue)}")

    if not in_venue:
        print("  FAIL: no papers in allowlisted venues — check venue matching")
        return

    print(f"\n  Sample seed papers:")
    for p in in_venue[:5]:
        print(f"    {p.year}  {p.venue:35s}  {p.title[:60]}")

    # Expand citations from the most-cited seed paper.
    in_venue.sort(key=lambda p: -p.citation_count)
    most_cited = in_venue[0]
    print(f"\n[3/3] Fetching citations for most-cited seed paper:")
    print(
        f"  {most_cited.title!r} ({most_cited.year}, {most_cited.citation_count} citations)"
    )
    citations = loader.fetch_paper_citations(
        most_cited.paper_id,
        year_start=2015,
        year_end=2025,
        limit=200,
    )
    print(f"  Got {len(citations)} citing papers in window")

    citing_in_venue = [p for p in citations if venue_matches(p.venue)]
    print(f"  Of which in econ venue allowlist: {len(citing_in_venue)}")

    print(f"\n  Sample citing papers (top 5 by citation count):")
    citing_in_venue.sort(key=lambda p: -p.citation_count)
    for p in citing_in_venue[:5]:
        print(f"    {p.year}  {p.venue:35s}  {p.title[:60]}")

    # Diagnostic
    print()
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"  Seed papers (post-filter):  {len(in_venue)}")
    print(f"  Citations from one paper:    {len(citing_in_venue)}")
    print()

    if len(citing_in_venue) >= 5:
        print("  HEALTHY: citation expansion is producing meaningful results.")
        print("  Next step: python scripts/pull_corpus.py")
    elif len(citing_in_venue) > 0:
        print("  MARGINAL: citation expansion works but yield is low.")
        print("  Full pull will likely produce a smaller corpus than hoped.")
    else:
        print("  PROBLEM: citation expansion produced zero filtered results.")
        print("  Investigate before running the full pull.")


if __name__ == "__main__":
    main()
