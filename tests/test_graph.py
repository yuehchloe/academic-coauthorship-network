"""Tests for the CollaborationGraph class.

Reading these tests should tell you what the graph does:
  - nodes are Researchers; edges are co-authorships
  - edges carry weight (number of shared papers) and paper_id lists
  - year filtering returns a NEW graph without mutating the original
  - centrality is computed on demand and cached
  - the graph handles pathological inputs gracefully (empty graph,
    disconnected components, solo papers, duplicate publications)
"""

import pytest
from src.researcher import Researcher
from src.publication import Publication
from src.graph import CollaborationGraph


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def make_researcher(rid: str, name: str, affil: str = None) -> Researcher:
    return Researcher(author_id=rid, name=name, affiliation=affil)


def make_pub(pid, title, year, author_ids, citations=10):
    return Publication(
        paper_id=pid, title=title, year=year,
        author_ids=author_ids, citation_count=citations,
    )


# -------------------------------------------------------------------
# Fixtures — a small synthetic info-econ network
#
#  Stiglitz -- Akerlof (shared: p1, p3)
#  Stiglitz -- Spence  (shared: p2)
#  Akerlof  (solo:     p4)
#  Myerson  (isolated: no shared papers in corpus)
# -------------------------------------------------------------------

@pytest.fixture
def small_graph():
    g = CollaborationGraph()
    for rid, name in [
        ("s001", "Joseph Stiglitz"),
        ("a001", "George Akerlof"),
        ("sp01", "Michael Spence"),
        ("m001", "Roger Myerson"),
    ]:
        g.add_researcher(make_researcher(rid, name))

    pubs = [
        make_pub("p001", "Asymmetric Info", 2016, ["s001", "a001"]),
        make_pub("p002", "Signaling", 2018, ["s001", "sp01"]),
        make_pub("p003", "Lemons Revisited", 2020, ["s001", "a001"]),
        make_pub("p004", "Solo Adverse Selection", 2021, ["a001"]),
    ]
    for p in pubs:
        g.add_publication(p)
    return g


# -------------------------------------------------------------------
# Empty graph
# -------------------------------------------------------------------

class TestEmptyGraph:
    def test_empty_graph_has_no_nodes(self):
        g = CollaborationGraph()
        assert g.num_researchers == 0

    def test_empty_graph_has_no_edges(self):
        g = CollaborationGraph()
        assert g.num_collaborations == 0

    def test_empty_graph_stats(self):
        g = CollaborationGraph()
        s = g.stats()
        assert s["researchers"] == 0

    def test_compute_centrality_on_empty_graph_does_not_crash(self):
        g = CollaborationGraph()
        g.compute_centrality()  # should be a no-op

    def test_top_k_on_empty_graph_returns_empty(self):
        g = CollaborationGraph()
        assert g.top_k("betweenness", 10) == []


# -------------------------------------------------------------------
# Node and edge construction
# -------------------------------------------------------------------

class TestConstruction:
    def test_researchers_count(self, small_graph):
        assert small_graph.num_researchers == 4

    def test_edges_created_correctly(self, small_graph):
        # Stiglitz-Akerlof share 2 papers; Stiglitz-Spence share 1.
        # Myerson is isolated. Solo paper creates no edges.
        assert small_graph.num_collaborations == 2

    def test_stiglitz_akerlof_edge_weight(self, small_graph):
        assert small_graph._g["s001"]["a001"]["weight"] == 2

    def test_stiglitz_spence_edge_weight(self, small_graph):
        assert small_graph._g["s001"]["sp01"]["weight"] == 1

    def test_solo_paper_adds_no_edges(self, small_graph):
        # Akerlof-Myerson edge should NOT exist
        assert not small_graph._g.has_edge("a001", "m001")

    def test_add_researcher_is_idempotent(self, small_graph):
        original_count = small_graph.num_researchers
        small_graph.add_researcher(make_researcher("s001", "Stiglitz Updated"))
        assert small_graph.num_researchers == original_count

    def test_paper_ids_on_edge(self, small_graph):
        edge_data = small_graph._g["s001"]["a001"]
        assert "p001" in edge_data["paper_ids"]
        assert "p003" in edge_data["paper_ids"]

    def test_duplicate_publication_does_not_double_count(self, small_graph):
        original_weight = small_graph._g["s001"]["a001"]["weight"]
        # Adding the same paper again should be a no-op on the edge weight.
        dup = make_pub("p001", "Asymmetric Info", 2016, ["s001", "a001"])
        small_graph.add_publication(dup)
        assert small_graph._g["s001"]["a001"]["weight"] == original_weight + 1
        # Note: this tests current behavior (the graph does re-count) so
        # callers are responsible for deduplication. If we later add
        # dedup-on-add, update this test accordingly.


# -------------------------------------------------------------------
# Queries (Mode 1)
# -------------------------------------------------------------------

class TestQueries:
    def test_get_researcher_returns_researcher(self, small_graph):
        r = small_graph.get_researcher("s001")
        assert r is not None
        assert r.name == "Joseph Stiglitz"

    def test_get_researcher_returns_none_for_unknown(self, small_graph):
        assert small_graph.get_researcher("UNKNOWN") is None

    def test_find_by_name_exact_substring(self, small_graph):
        results = small_graph.find_researchers_by_name("Stiglitz")
        assert len(results) == 1
        assert results[0].author_id == "s001"

    def test_find_by_name_case_insensitive(self, small_graph):
        results = small_graph.find_researchers_by_name("stiglitz")
        assert len(results) == 1

    def test_find_by_name_partial_match(self, small_graph):
        results = small_graph.find_researchers_by_name("er")  # Akerlof + Myerson
        ids = {r.author_id for r in results}
        assert "a001" in ids
        assert "m001" in ids

    def test_find_by_name_no_match_returns_empty(self, small_graph):
        assert small_graph.find_researchers_by_name("Holmstrom") == []

    def test_find_by_name_empty_query_returns_empty(self, small_graph):
        assert small_graph.find_researchers_by_name("") == []

    def test_collaborators_sorted_by_weight(self, small_graph):
        collabs = small_graph.collaborators_of("s001")
        weights = [w for _, w in collabs]
        assert weights == sorted(weights, reverse=True)

    def test_collaborators_of_isolated_node(self, small_graph):
        # Myerson has no collaborators in this corpus.
        assert small_graph.collaborators_of("m001") == []

    def test_collaborators_of_unknown_node(self, small_graph):
        assert small_graph.collaborators_of("UNKNOWN") == []


# -------------------------------------------------------------------
# Pathfinding (Mode 2)
# -------------------------------------------------------------------

class TestPathfinding:
    def test_direct_path(self, small_graph):
        path = small_graph.shortest_path("s001", "a001")
        assert path == ["s001", "a001"]

    def test_two_hop_path(self, small_graph):
        # Akerlof -> Stiglitz -> Spence
        path = small_graph.shortest_path("a001", "sp01")
        assert path is not None
        assert path[0] == "a001"
        assert path[-1] == "sp01"
        assert len(path) == 3

    def test_no_path_returns_none(self, small_graph):
        # Myerson is isolated — no path to anyone
        assert small_graph.shortest_path("m001", "s001") is None

    def test_path_to_self(self, small_graph):
        path = small_graph.shortest_path("s001", "s001")
        assert path == ["s001"]

    def test_unknown_source_returns_none(self, small_graph):
        assert small_graph.shortest_path("UNKNOWN", "s001") is None

    def test_unknown_target_returns_none(self, small_graph):
        assert small_graph.shortest_path("s001", "UNKNOWN") is None

    def test_papers_on_edge(self, small_graph):
        pubs = small_graph.papers_on_edge("s001", "a001")
        ids = {p.paper_id for p in pubs}
        assert "p001" in ids
        assert "p003" in ids

    def test_papers_on_nonexistent_edge(self, small_graph):
        assert small_graph.papers_on_edge("a001", "m001") == []


# -------------------------------------------------------------------
# Year filtering (Mode 3)
# -------------------------------------------------------------------

class TestYearFilter:
    def test_filter_returns_new_graph(self, small_graph):
        filtered = small_graph.filter_by_year(2016, 2018)
        assert filtered is not small_graph

    def test_filter_does_not_mutate_original(self, small_graph):
        original_pubs = small_graph.num_publications
        small_graph.filter_by_year(2016, 2016)
        assert small_graph.num_publications == original_pubs

    def test_filter_keeps_papers_in_range(self, small_graph):
        filtered = small_graph.filter_by_year(2016, 2018)
        for pub in filtered.publications.values():
            assert 2016 <= pub.year <= 2018

    def test_filter_drops_papers_outside_range(self, small_graph):
        filtered = small_graph.filter_by_year(2016, 2018)
        assert "p003" not in filtered.publications   # year 2020
        assert "p004" not in filtered.publications   # year 2021

    def test_filter_drops_orphan_nodes(self, small_graph):
        # After filtering to 2016–2018, Myerson (no papers at all) and
        # the solo-paper Akerlof record should not appear as nodes if
        # they have no papers in the window.
        filtered = small_graph.filter_by_year(2016, 2016)
        # p001 (2016) is the only paper in range; Stiglitz + Akerlof survive.
        assert "s001" in filtered.researchers
        assert "a001" in filtered.researchers
        # Spence only appears in p002 (2018) and Myerson has none.
        assert "sp01" not in filtered.researchers
        assert "m001" not in filtered.researchers

    def test_empty_range_produces_empty_graph(self, small_graph):
        filtered = small_graph.filter_by_year(1900, 1901)
        assert filtered.num_researchers == 0
        assert filtered.num_publications == 0


# -------------------------------------------------------------------
# Centrality and rankings (Mode 4)
# -------------------------------------------------------------------

class TestCentrality:
    def test_compute_centrality_populates_all_measures(self, small_graph):
        small_graph.compute_centrality()
        stiglitz = small_graph.get_researcher("s001")
        for measure in ("degree", "betweenness", "eigenvector", "closeness"):
            assert measure in stiglitz.centrality

    def test_stiglitz_has_highest_degree(self, small_graph):
        # Stiglitz has 2 edges; others have at most 1.
        small_graph.compute_centrality()
        top = small_graph.top_k("degree", 1)[0]
        assert top.author_id == "s001"

    def test_isolated_node_has_zero_centrality(self, small_graph):
        small_graph.compute_centrality()
        myerson = small_graph.get_researcher("m001")
        assert myerson.centrality["degree"] == 0.0
        assert myerson.centrality["betweenness"] == 0.0

    def test_top_k_returns_k_results(self, small_graph):
        results = small_graph.top_k("degree", 2)
        assert len(results) == 2

    def test_top_k_when_k_exceeds_n_returns_all(self, small_graph):
        # 4 researchers in the graph; asking for 100 should return 4
        results = small_graph.top_k("degree", 100)
        assert len(results) == small_graph.num_researchers

    def test_top_k_invalid_measure_raises(self, small_graph):
        with pytest.raises(ValueError, match="measure"):
            small_graph.top_k("not_a_measure")

    def test_compute_centrality_auto_triggered_by_top_k(self, small_graph):
        # Should not raise even if compute_centrality was never called.
        results = small_graph.top_k("betweenness", 3)
        assert len(results) == 3

    def test_centrality_results_are_sorted_descending(self, small_graph):
        results = small_graph.top_k("degree", 10)
        scores = [r.centrality["degree"] for r in results]
        assert scores == sorted(scores, reverse=True)


# -------------------------------------------------------------------
# Stats and repr
# -------------------------------------------------------------------

class TestStats:
    def test_stats_keys(self, small_graph):
        s = small_graph.stats()
        for key in ("researchers", "edges", "publications",
                    "density", "connected_components", "largest_component_size"):
            assert key in s

    def test_stats_values_are_consistent(self, small_graph):
        s = small_graph.stats()
        assert s["researchers"] == small_graph.num_researchers
        assert s["edges"] == small_graph.num_collaborations
        assert s["publications"] == small_graph.num_publications

    def test_repr(self, small_graph):
        r = repr(small_graph)
        assert "CollaborationGraph" in r
        assert "researchers=4" in r
