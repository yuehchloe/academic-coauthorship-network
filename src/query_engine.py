"""
QueryEngine — a thin facade over CollaborationGraph that maps directly onto
the four required interaction modes.

The point of this class is separation of concerns: the Streamlit app talks
to QueryEngine, never directly to the graph. That way the UI layer doesn't
know anything about networkx and can be swapped (CLI, web, notebook) without
touching graph logic.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .graph import CollaborationGraph
from .researcher import Researcher
from .publication import Publication


@dataclass
class ResearcherProfile:
    """Bundle of info shown on the Search & Query view (Mode 1)."""
    researcher: Researcher
    top_collaborators: list[tuple[Researcher, int]]
    publications: list[Publication]
    centrality_rank: dict[str, int]  # rank within the corpus, 1-indexed


@dataclass
class PathResult:
    """Bundle of info shown on the Pathfinding view (Mode 2)."""
    found: bool
    researchers: list[Researcher]              # nodes along the path
    bridging_papers: list[list[Publication]]   # papers per edge
    distance: int

    @classmethod
    def not_found(cls) -> "PathResult":
        return cls(found=False, researchers=[], bridging_papers=[], distance=-1)


class QueryEngine:
    """High-level interface for the Streamlit app and CLI."""

    def __init__(self, graph: CollaborationGraph) -> None:
        self.graph = graph
        if graph.num_researchers > 0:
            graph.compute_centrality(
                betweenness_k=500 if graph.num_researchers > 2000 else None
            )

    # --- Mode 1: Search & Query --------------------------------------

    def search(self, name_query: str) -> list[Researcher]:
        return self.graph.find_researchers_by_name(name_query)

    def profile(self, author_id: str) -> Optional[ResearcherProfile]:
        r = self.graph.get_researcher(author_id)
        if r is None:
            return None
        collabs = self.graph.collaborators_of(author_id)[:10]
        pubs = [self.graph.publications[pid]
                for pid in r.paper_ids
                if pid in self.graph.publications]
        pubs.sort(key=lambda p: -(p.year or 0))
        return ResearcherProfile(
            researcher=r,
            top_collaborators=collabs,
            publications=pubs,
            centrality_rank=self._compute_ranks(author_id),
        )

    def _compute_ranks(self, author_id: str) -> dict[str, int]:
        ranks = {}
        for measure in ("degree", "betweenness", "eigenvector", "closeness"):
            ordered = sorted(
                self.graph.researchers.values(),
                key=lambda r: -r.centrality.get(measure, 0.0),
            )
            for i, r in enumerate(ordered, 1):
                if r.author_id == author_id:
                    ranks[measure] = i
                    break
        return ranks

    # --- Mode 2: Pathfinding -----------------------------------------

    def find_path(self, source_id: str, target_id: str) -> PathResult:
        path = self.graph.shortest_path(source_id, target_id)
        if path is None:
            return PathResult.not_found()
        researchers = [self.graph.researchers[aid] for aid in path]
        bridging = []
        for i in range(len(path) - 1):
            bridging.append(self.graph.papers_on_edge(path[i], path[i + 1]))
        return PathResult(
            found=True,
            researchers=researchers,
            bridging_papers=bridging,
            distance=len(path) - 1,
        )

    # --- Mode 3: Year filter -----------------------------------------

    def filter_by_year(self, start: int, end: int) -> "QueryEngine":
        """Returns a NEW QueryEngine over the year-filtered subgraph."""
        sub = self.graph.filter_by_year(start, end)
        return QueryEngine(sub)

    # --- Mode 4: Rankings --------------------------------------------

    def top_central(self, measure: str = "betweenness", k: int = 10) -> list[Researcher]:
        return self.graph.top_k(measure, k)

    def rankings_table(self, k: int = 10) -> dict[str, list[Researcher]]:
        """Side-by-side rankings for all four measures. This is what powers
        the headline "intellectual monopolies" view."""
        return {
            measure: self.top_central(measure, k)
            for measure in ("degree", "betweenness", "eigenvector", "closeness")
        }

    # --- Stats -------------------------------------------------------

    def corpus_summary(self) -> dict:
        return self.graph.stats()
