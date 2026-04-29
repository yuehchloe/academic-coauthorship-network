"""
CollaborationGraph — the core graph structure.

Wraps a networkx.Graph rather than inheriting from it. Composition keeps the
public surface controlled and lets us add domain-specific methods (centrality
caching, year-filtering, top-k queries) without exposing the full networkx API.

Nodes:  Researcher.author_id (string)
Edges:  Co-authorship. weight = number of papers two authors share in the corpus.
        Each edge stores the list of paper_ids that produced it.
"""

from __future__ import annotations
from typing import Optional
import networkx as nx

from .researcher import Researcher
from .publication import Publication


class CollaborationGraph:
    """Co-authorship graph for the information-economics corpus.

    Implementation note: we keep the Researcher and Publication objects in
    parallel dicts and store only the author_id strings on the networkx graph
    itself. This keeps the graph serializable and avoids stale-object bugs.
    """

    def __init__(self) -> None:
        self._g: nx.Graph = nx.Graph()
        self.researchers: dict[str, Researcher] = {}
        self.publications: dict[str, Publication] = {}
        self._centrality_cached: bool = False

    # ---------------------------------------------------------------
    # Construction
    # ---------------------------------------------------------------

    def add_researcher(self, researcher: Researcher) -> None:
        """Add a researcher as a node. Idempotent — re-adding a known
        researcher updates the stored object but doesn't duplicate the node."""
        self.researchers[researcher.author_id] = researcher
        if not self._g.has_node(researcher.author_id):
            self._g.add_node(researcher.author_id)
        self._centrality_cached = False

    def add_publication(self, pub: Publication) -> None:
        """Add a publication and create co-authorship edges between every
        pair of its authors. Authors must already be added as researchers."""
        self.publications[pub.paper_id] = pub

        for a, b in pub.coauthor_pairs():
            if a not in self.researchers or b not in self.researchers:
                # Skip pairs where we don't have full researcher records.
                # This can happen if the API returned a paper but we couldn't
                # batch-fetch some of its authors.
                continue

            self.researchers[a].add_paper(pub.paper_id)
            self.researchers[b].add_paper(pub.paper_id)

            if self._g.has_edge(a, b):
                self._g[a][b]["weight"] += 1
                self._g[a][b]["paper_ids"].append(pub.paper_id)
            else:
                self._g.add_edge(a, b, weight=1, paper_ids=[pub.paper_id])

        # Solo papers still belong to their author's paper set.
        if not pub.is_collaborative and pub.author_ids:
            sole = pub.author_ids[0]
            if sole in self.researchers:
                self.researchers[sole].add_paper(pub.paper_id)

        self._centrality_cached = False

    # ---------------------------------------------------------------
    # Basic queries (Mode 1: Search & Query)
    # ---------------------------------------------------------------

    def get_researcher(self, author_id: str) -> Optional[Researcher]:
        return self.researchers.get(author_id)

    def find_researchers_by_name(self, name_query: str) -> list[Researcher]:
        """Case-insensitive substring search over names."""
        q = name_query.lower().strip()
        if not q:
            return []
        return [r for r in self.researchers.values() if q in r.name.lower()]

    def collaborators_of(self, author_id: str) -> list[tuple[Researcher, int]]:
        """Return (collaborator, num_shared_papers) sorted by shared papers desc."""
        if not self._g.has_node(author_id):
            return []
        out = []
        for nbr in self._g.neighbors(author_id):
            weight = self._g[author_id][nbr]["weight"]
            out.append((self.researchers[nbr], weight))
        out.sort(key=lambda x: -x[1])
        return out

    # ---------------------------------------------------------------
    # Pathfinding (Mode 2)
    # ---------------------------------------------------------------

    def shortest_path(
        self, source_id: str, target_id: str
    ) -> Optional[list[str]]:
        """Return list of author_ids along the shortest path, or None if
        no path exists. Uses unweighted BFS (Erdős-number style)."""
        if source_id not in self._g or target_id not in self._g:
            return None
        try:
            return nx.shortest_path(self._g, source_id, target_id)
        except nx.NetworkXNoPath:
            return None

    def papers_on_edge(self, a: str, b: str) -> list[Publication]:
        """Get the actual papers that connect two adjacent authors.
        Used by the LLM narrative feature."""
        if not self._g.has_edge(a, b):
            return []
        ids = self._g[a][b]["paper_ids"]
        return [self.publications[pid] for pid in ids if pid in self.publications]

    # ---------------------------------------------------------------
    # Filtering (Mode 3)
    # ---------------------------------------------------------------

    def filter_by_year(
        self, start_year: int, end_year: int
    ) -> "CollaborationGraph":
        """Return a NEW CollaborationGraph containing only papers from
        [start_year, end_year] inclusive, plus any researchers who appear
        on those papers. Original graph is untouched."""
        sub = CollaborationGraph()
        for r in self.researchers.values():
            sub.add_researcher(
                Researcher(
                    author_id=r.author_id,
                    name=r.name,
                    affiliation=r.affiliation,
                    citation_count=r.citation_count,
                    h_index=r.h_index,
                )
            )
        for pub in self.publications.values():
            if pub.year is not None and start_year <= pub.year <= end_year:
                sub.add_publication(pub)

        # Drop researchers with no papers in the filtered window.
        orphans = [aid for aid, r in sub.researchers.items()
                   if r.paper_count_in_corpus == 0]
        for aid in orphans:
            sub._g.remove_node(aid)
            del sub.researchers[aid]
        return sub

    # ---------------------------------------------------------------
    # Centrality / Rankings (Mode 4)
    # ---------------------------------------------------------------

    def compute_centrality(self, betweenness_k: Optional[int] = None) -> None:
        """Compute degree, betweenness, eigenvector, closeness centrality
        and attach to each Researcher's .centrality dict.

        betweenness_k: if set, use approximate betweenness sampling k nodes.
            Recommended for graphs with >2000 nodes.
        """
        if self._g.number_of_nodes() == 0:
            return

        deg = nx.degree_centrality(self._g)

        if betweenness_k and betweenness_k < self._g.number_of_nodes():
            btw = nx.betweenness_centrality(self._g, k=betweenness_k, seed=42)
        else:
            btw = nx.betweenness_centrality(self._g)

        # Eigenvector requires connected component. Use largest if disconnected.
        try:
            if nx.is_connected(self._g):
                eig = nx.eigenvector_centrality(self._g, max_iter=1000)
            else:
                largest_cc = max(nx.connected_components(self._g), key=len)
                sub = self._g.subgraph(largest_cc)
                eig_partial = nx.eigenvector_centrality(sub, max_iter=1000)
                eig = {n: eig_partial.get(n, 0.0) for n in self._g.nodes()}
        except nx.PowerIterationFailedConvergence:
            eig = {n: 0.0 for n in self._g.nodes()}

        clo = nx.closeness_centrality(self._g)

        for aid, researcher in self.researchers.items():
            researcher.centrality = {
                "degree": deg.get(aid, 0.0),
                "betweenness": btw.get(aid, 0.0),
                "eigenvector": eig.get(aid, 0.0),
                "closeness": clo.get(aid, 0.0),
            }
        self._centrality_cached = True

    def top_k(self, measure: str, k: int = 10) -> list[Researcher]:
        """Return top-k researchers by the given centrality measure.
        Auto-computes centrality if not yet cached."""
        valid = {"degree", "betweenness", "eigenvector", "closeness"}
        if measure not in valid:
            raise ValueError(f"measure must be one of {valid}, got {measure!r}")
        if not self._centrality_cached:
            self.compute_centrality()
        ranked = sorted(
            self.researchers.values(),
            key=lambda r: -r.centrality.get(measure, 0.0),
        )
        return ranked[:k]

    # ---------------------------------------------------------------
    # Stats / introspection
    # ---------------------------------------------------------------

    @property
    def num_researchers(self) -> int:
        return self._g.number_of_nodes()

    @property
    def num_collaborations(self) -> int:
        return self._g.number_of_edges()

    @property
    def num_publications(self) -> int:
        return len(self.publications)

    def stats(self) -> dict:
        """Summary stats for display."""
        if self._g.number_of_nodes() == 0:
            return {"researchers": 0, "edges": 0, "publications": 0}
        return {
            "researchers": self.num_researchers,
            "edges": self.num_collaborations,
            "publications": self.num_publications,
            "density": nx.density(self._g),
            "connected_components": nx.number_connected_components(self._g),
            "largest_component_size": len(
                max(nx.connected_components(self._g), key=len)
            ),
        }

    def __repr__(self) -> str:
        return (
            f"CollaborationGraph(researchers={self.num_researchers}, "
            f"edges={self.num_collaborations}, "
            f"publications={self.num_publications})"
        )
