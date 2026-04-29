"""
Pull the full corpus from Semantic Scholar.

Run from project root:
    python scripts/pull_corpus.py

This runs all six seed queries, deduplicates papers across them,
batch-fetches author records, and saves a hydrated CollaborationGraph
to data/corpus.json. Subsequent runs reuse the cache.

Tunables at top of file. Default settings produce ~600-1200 papers depending
on what S2 has indexed for these queries.
"""

import sys
import json
import logging
from pathlib import Path

# Allow running from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_loader import DataLoader
from src.publication import Publication
from src.venues import TOP_ECON_VENUE_PATTERNS


# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

# Twelve diagnostic info-econ queries. Each is a phrase that authors in
# this subfield use to label their own work. Tier 1 is most canonical,
# Tier 3 is more specialized. Phrases like "asymmetric information" and
# "learning" were excluded because they pull too much noise from CS/ML
# and behavioral economics respectively.
SEED_QUERIES = [
    "adverse selection",
    "moral hazard",
    "mechanism design",
    "principal agent",
    "Bayesian persuasion",
    "cheap talk",
    "incentive compatibility",
    "revelation principle",
    "signaling equilibrium",
    "screening contract",
    "auction theory",
    "rational inattention",
]

YEAR_START = 2015
YEAR_END = 2025
PER_QUERY_LIMIT = 500  # cap per query; total before dedup ~= 12 * this
FIELDS_OF_STUDY = ["Economics"]
VENUE_ALLOWLIST = TOP_ECON_VENUE_PATTERNS
CACHE_DIR = "data/cache"
OUTPUT_PATH = "data/corpus.json"
API_KEY = None  # set via env var if you have one


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

    # 1. Pull each seed query.
    all_papers: dict[str, Publication] = {}
    per_query_counts: dict[str, int] = {}
    for query in SEED_QUERIES:
        papers = loader.search_papers(
            query,
            year_start=YEAR_START,
            year_end=YEAR_END,
            limit=PER_QUERY_LIMIT,
            fields_of_study=FIELDS_OF_STUDY,
            venue_allowlist=VENUE_ALLOWLIST,
        )
        per_query_counts[query] = len(papers)
        new_in_this_query = 0
        for p in papers:
            if p.paper_id not in all_papers:
                all_papers[p.paper_id] = p
                new_in_this_query += 1
        log.info(
            "Query %r: %d papers (%d new, %d duplicate)",
            query,
            len(papers),
            new_in_this_query,
            len(papers) - new_in_this_query,
        )

    log.info("Total unique papers across all queries: %d", len(all_papers))

    # 2. Build the hydrated graph (this triggers author batch fetch).
    graph = loader.build_graph(list(all_papers.values()), fetch_full_authors=True)
    graph.compute_centrality(
        betweenness_k=500 if graph.num_researchers > 2000 else None
    )

    log.info("Graph built: %s", graph)
    log.info("Stats: %s", graph.stats())

    # 3. Persist.
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "queries": SEED_QUERIES,
            "year_range": [YEAR_START, YEAR_END],
            "per_query_counts": per_query_counts,
            "total_papers": len(all_papers),
        },
        "researchers": [r.to_dict() for r in graph.researchers.values()],
        "publications": [p.to_dict() for p in graph.publications.values()],
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    log.info("Saved corpus to %s", OUTPUT_PATH)

    # 4. Quick sanity report.
    print()
    print("=" * 60)
    print("CORPUS SUMMARY")
    print("=" * 60)
    for q, n in per_query_counts.items():
        print(f"  {q:40s}  {n:>4d} papers")
    print(f"  {'TOTAL UNIQUE':40s}  {len(all_papers):>4d} papers")
    print()
    print(f"  Researchers:           {graph.num_researchers}")
    print(f"  Co-author edges:       {graph.num_collaborations}")
    print(f"  Connected components:  {graph.stats()['connected_components']}")
    print(f"  Largest component:     {graph.stats()['largest_component_size']} authors")
    print()
    print("Top 10 by betweenness centrality:")
    for r in graph.top_k("betweenness", 10):
        affil = r.affiliation or "—"
        print(f"  {r.centrality['betweenness']:.4f}  {r.name:30s}  ({affil})")


if __name__ == "__main__":
    main()
