"""
Pull the corpus via author-anchored citation-graph expansion.

Strategy:
    1. For each seed author, resolve their S2 authorId via name search.
    2. Fetch each seed author's papers in [YEAR_START, YEAR_END].
    3. Filter those papers to our econ venue allowlist (the seed papers
       must themselves be published in legitimate venues).
    4. For each surviving seed paper, fetch papers that cite it; filter
       the citing papers by venue + year.
    5. Dedupe across all seeds. Build the graph.

Why this works:
    Keyword search produced a fragmented graph (269 components on 658
    nodes) because each paper had ~2 authors and most authors appeared
    in only one paper within the corpus. Citation expansion multiplies
    density: every seed paper drags 50+ citing papers along with it,
    raising the chance that any two authors share at least one paper.

Tradeoff acknowledged:
    The corpus is built around the seed authors, so they will tend to
    rank highly on centrality measures by construction. We accept this
    and document it. The interesting finding is which NON-seed authors
    rise to high centrality — those are the actual gatekeepers.

Run from project root:
    python scripts/pull_corpus.py
"""

import sys
import json
import logging
from pathlib import Path
import os

# Allow running from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_loader import DataLoader
from src.publication import Publication
from src.venues import TOP_ECON_VENUE_PATTERNS, venue_matches
from src.seed_authors import SEED_AUTHORS


# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

YEAR_START = 2015
YEAR_END = 2025
SEED_PAPER_LIMIT = 200  # max seed papers per author
CITATION_LIMIT = 200  # max citing papers per seed paper
MIN_CITATIONS_TO_EXPAND = 1  # only expand from papers with >= N citations
CACHE_DIR = "data/cache"
OUTPUT_PATH = "data/corpus.json"
API_KEY = os.environ.get("S2_API_KEY")  # set via env var if you have one


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def venue_filter(publications: list[Publication]) -> list[Publication]:
    """Drop papers whose venue isn't in the econ allowlist."""
    return [p for p in publications if venue_matches(p.venue)]


def year_filter(publications: list[Publication]) -> list[Publication]:
    """Drop papers outside [YEAR_START, YEAR_END]."""
    return [
        p
        for p in publications
        if p.year is not None and YEAR_START <= p.year <= YEAR_END
    ]


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("pull_corpus")

    loader = DataLoader(cache_dir=CACHE_DIR, api_key=API_KEY)

    # Stage 1: resolve seed authors -> authorIds
    log.info("=" * 60)
    log.info("STAGE 1: Resolving seed authors")
    log.info("=" * 60)
    resolved: list[tuple[str, str]] = []  # (display_name, authorId)
    for display_name, hardcoded_id, _ in SEED_AUTHORS:
        if hardcoded_id:
            resolved.append((display_name, hardcoded_id))
            continue
        author_id = loader.resolve_author_by_name(display_name)
        if author_id:
            resolved.append((display_name, author_id))
        else:
            log.warning("Could not resolve %r — skipping", display_name)

    log.info("Resolved %d/%d seed authors", len(resolved), len(SEED_AUTHORS))

    # Stage 2: fetch seed papers per author, venue+year filter
    log.info("=" * 60)
    log.info("STAGE 2: Fetching seed papers")
    log.info("=" * 60)
    seed_papers: dict[str, Publication] = {}
    seed_paper_counts: dict[str, int] = {}
    for display_name, author_id in resolved:
        raw = loader.fetch_author_papers(
            author_id,
            year_start=YEAR_START,
            year_end=YEAR_END,
            limit=SEED_PAPER_LIMIT,
        )
        filtered = venue_filter(raw)
        seed_paper_counts[display_name] = len(filtered)
        log.info(
            "  %-25s  %3d papers in window, %3d in econ venues",
            display_name,
            len(raw),
            len(filtered),
        )
        for p in filtered:
            if p.paper_id not in seed_papers:
                seed_papers[p.paper_id] = p

    log.info("Total unique seed papers: %d", len(seed_papers))

    # Stage 3: expand each seed paper via citations, venue+year filter
    log.info("=" * 60)
    log.info("STAGE 3: Expanding via citations")
    log.info("=" * 60)
    all_papers: dict[str, Publication] = dict(seed_papers)
    citations_added = 0
    for i, (paper_id, seed) in enumerate(seed_papers.items(), 1):
        if seed.citation_count < MIN_CITATIONS_TO_EXPAND:
            continue
        if i % 25 == 0:
            log.info(
                "  Progress: expanded %d/%d seed papers, corpus size %d",
                i,
                len(seed_papers),
                len(all_papers),
            )
        citing = loader.fetch_paper_citations(
            paper_id,
            year_start=YEAR_START,
            year_end=YEAR_END,
            limit=CITATION_LIMIT,
        )
        filtered = venue_filter(citing)
        for p in filtered:
            if p.paper_id not in all_papers:
                all_papers[p.paper_id] = p
                citations_added += 1

    log.info(
        "Citations added %d papers; total unique: %d",
        citations_added,
        len(all_papers),
    )

    # Stage 4: build the hydrated graph
    log.info("=" * 60)
    log.info("STAGE 4: Building graph")
    log.info("=" * 60)
    graph = loader.build_graph(list(all_papers.values()), fetch_full_authors=True)
    graph.compute_centrality(
        betweenness_k=500 if graph.num_researchers > 2000 else None,
    )
    log.info("Graph: %s", graph)
    log.info("Stats: %s", graph.stats())

    # Stage 5: persist
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "strategy": "author-anchored citation expansion",
            "seed_authors": [n for n, _, _ in SEED_AUTHORS],
            "year_range": [YEAR_START, YEAR_END],
            "seed_paper_counts": seed_paper_counts,
            "total_seed_papers": len(seed_papers),
            "total_papers": len(all_papers),
        },
        "researchers": [r.to_dict() for r in graph.researchers.values()],
        "publications": [p.to_dict() for p in graph.publications.values()],
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    log.info("Saved corpus to %s", OUTPUT_PATH)

    # Final report
    print()
    print("=" * 60)
    print("CORPUS SUMMARY")
    print("=" * 60)
    print(f"  Seed authors resolved:    {len(resolved)}/{len(SEED_AUTHORS)}")
    print(f"  Seed papers (post-filter): {len(seed_papers)}")
    print(f"  Citation expansion added:  {citations_added} papers")
    print(f"  TOTAL unique papers:       {len(all_papers)}")
    print()
    print(f"  Researchers:           {graph.num_researchers}")
    print(f"  Co-author edges:       {graph.num_collaborations}")
    stats = graph.stats()
    print(f"  Connected components:  {stats['connected_components']}")
    print(f"  Largest component:     {stats['largest_component_size']} authors")
    largest_pct = 100 * stats["largest_component_size"] / max(graph.num_researchers, 1)
    print(f"  Largest comp share:    {largest_pct:.1f}% of authors")
    print()
    print("Top 10 by betweenness centrality:")
    for r in graph.top_k("betweenness", 10):
        affil = r.affiliation or "—"
        print(f"  {r.centrality['betweenness']:.4f}  {r.name:30s}  ({affil})")


if __name__ == "__main__":
    main()
