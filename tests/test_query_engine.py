"""Tests for the QueryEngine class.

Reading these tests should tell you what each interaction mode does and
what it returns. The QueryEngine is the contract between the graph layer
and the Streamlit/CLI UI layer.
"""

import pytest
from src.researcher import Researcher
from src.publication import Publication
from src.graph import CollaborationGraph
from src.query_engine import QueryEngine, ResearcherProfile, PathResult


# -------------------------------------------------------------------
# Helpers & fixtures
# -------------------------------------------------------------------


def make_researcher(rid, name, affil=None, citations=0, h_index=0):
    return Researcher(
        author_id=rid,
        name=name,
        affiliation=affil,
        citation_count=citations,
        h_index=h_index,
    )


def make_pub(pid, title, year, author_ids, citations=5):
    return Publication(
        paper_id=pid,
        title=title,
        year=year,
        author_ids=author_ids,
        citation_count=citations,
    )


@pytest.fixture
def engine():
    """A small engine with four researchers across two connected clusters
    plus one isolated node.

    Cluster A: Stiglitz -- Akerlof -- Spence (chain)
    Cluster B: Myerson  (isolated)
    """
    g = CollaborationGraph()
    researchers = [
        make_researcher("s001", "Joseph Stiglitz", "Columbia", 120000, 80),
        make_researcher("a001", "George Akerlof", "Georgetown", 50000, 60),
        make_researcher("sp01", "Michael Spence", "Stanford", 40000, 55),
        make_researcher("m001", "Roger Myerson", "Chicago", 25000, 50),
    ]
    for r in researchers:
        g.add_researcher(r)

    pubs = [
        make_pub("p001", "Info Asymmetry", 2016, ["s001", "a001"], 100),
        make_pub("p002", "Signaling Model", 2018, ["a001", "sp01"], 80),
        make_pub("p003", "Adverse Selection", 2020, ["s001", "a001"], 60),
        make_pub("p004", "Solo Mechanism", 2021, ["m001"], 30),
        make_pub("p005", "Three-author Paper", 2017, ["s001", "a001", "sp01"], 50),
    ]
    for p in pubs:
        g.add_publication(p)

    return QueryEngine(g)


# -------------------------------------------------------------------
# Mode 1: Search & Query
# -------------------------------------------------------------------


class TestSearchAndQuery:
    def test_search_returns_matching_researchers(self, engine):
        results = engine.search("Stiglitz")
        assert len(results) == 1
        assert results[0].author_id == "s001"

    def test_search_is_case_insensitive(self, engine):
        assert len(engine.search("stiglitz")) == 1

    def test_search_returns_multiple_matches(self, engine):
        # "e" appears in Spence and Myerson
        results = engine.search("e")
        assert len(results) >= 2

    def test_search_no_match_returns_empty(self, engine):
        assert engine.search("Holmstrom") == []

    def test_profile_returns_profile_object(self, engine):
        profile = engine.profile("s001")
        assert isinstance(profile, ResearcherProfile)

    def test_profile_contains_researcher(self, engine):
        profile = engine.profile("s001")
        assert profile.researcher.author_id == "s001"

    def test_profile_contains_top_collaborators(self, engine):
        profile = engine.profile("s001")
        collab_ids = {r.author_id for r, _ in profile.top_collaborators}
        # Stiglitz co-authored with Akerlof and Spence
        assert "a001" in collab_ids

    def test_profile_publications_sorted_recent_first(self, engine):
        profile = engine.profile("s001")
        years = [p.year for p in profile.publications if p.year]
        assert years == sorted(years, reverse=True)

    def test_profile_centrality_rank_is_populated(self, engine):
        profile = engine.profile("s001")
        for measure in ("degree", "betweenness", "eigenvector", "closeness"):
            assert measure in profile.centrality_rank
            assert isinstance(profile.centrality_rank[measure], int)

    def test_profile_returns_none_for_unknown(self, engine):
        assert engine.profile("UNKNOWN") is None

    def test_profile_stiglitz_ranks_near_top_by_degree(self, engine):
        # Stiglitz has most connections — should rank 1st by degree
        profile = engine.profile("s001")
        assert profile.centrality_rank["degree"] == 1


# -------------------------------------------------------------------
# Mode 2: Pathfinding
# -------------------------------------------------------------------


class TestPathfinding:
    def test_direct_path(self, engine):
        result = engine.find_path("s001", "a001")
        assert result.found
        assert result.distance == 1

    def test_two_hop_path(self, engine):
        # Stiglitz -> Akerlof -> Spence  OR  Stiglitz -> Spence (via p005)
        result = engine.find_path("s001", "sp01")
        assert result.found
        assert result.distance >= 1

    def test_path_researchers_list(self, engine):
        result = engine.find_path("s001", "a001")
        assert result.researchers[0].author_id == "s001"
        assert result.researchers[-1].author_id == "a001"

    def test_bridging_papers_populated(self, engine):
        result = engine.find_path("s001", "a001")
        # One edge, one list of bridging papers
        assert len(result.bridging_papers) == result.distance
        assert len(result.bridging_papers[0]) >= 1

    def test_no_path_to_isolated_node(self, engine):
        result = engine.find_path("s001", "m001")
        assert not result.found
        assert result.distance == -1

    def test_isolated_node_returns_out_of_scope(self, engine):
        # Myerson is isolated — should get not_in_component, not just not_found
        result = engine.find_path("s001", "m001")
        assert result.out_of_scope is True
        assert result.researchers == []

    def test_path_to_self(self, engine):
        result = engine.find_path("s001", "s001")
        assert result.found
        assert result.distance == 0

    def test_path_not_found_class_method(self):
        result = PathResult.not_found()
        assert not result.found
        assert result.distance == -1


# -------------------------------------------------------------------
# Mode 3: Year filtering
# -------------------------------------------------------------------


class TestYearFiltering:
    def test_filter_returns_new_query_engine(self, engine):
        filtered = engine.filter_by_year(2016, 2018)
        assert filtered is not engine

    def test_filtered_corpus_is_smaller(self, engine):
        filtered = engine.filter_by_year(2016, 2016)
        assert (
            filtered.corpus_summary()["publications"]
            < engine.corpus_summary()["publications"]
        )

    def test_filtered_graph_only_has_in_range_papers(self, engine):
        filtered = engine.filter_by_year(2016, 2016)
        for pub in filtered.graph.publications.values():
            assert pub.year == 2016

    def test_filter_empty_range_produces_empty_engine(self, engine):
        filtered = engine.filter_by_year(1900, 1901)
        assert filtered.corpus_summary()["researchers"] == 0

    def test_original_engine_unchanged_after_filter(self, engine):
        original_count = engine.corpus_summary()["publications"]
        engine.filter_by_year(2016, 2016)
        assert engine.corpus_summary()["publications"] == original_count


# -------------------------------------------------------------------
# Mode 4: Rankings
# -------------------------------------------------------------------


class TestRankings:
    def test_top_central_returns_k_results(self, engine):
        results = engine.top_central("betweenness", 3)
        assert len(results) == 3

    def test_top_central_default_k_is_10(self, engine):
        # 4 researchers in engine; asking for default 10 should return all 4
        results = engine.top_central("betweenness")
        assert len(results) <= 10
        assert len(results) == engine.graph.num_researchers

    def test_rankings_table_has_all_measures(self, engine):
        table = engine.rankings_table(k=3)
        for measure in ("degree", "betweenness", "eigenvector", "closeness"):
            assert measure in table
            assert len(table[measure]) == 3

    def test_rankings_are_sorted_descending(self, engine):
        for measure in ("degree", "betweenness", "eigenvector", "closeness"):
            results = engine.top_central(measure, 4)
            scores = [r.centrality[measure] for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_top_central_invalid_measure_raises(self, engine):
        with pytest.raises(ValueError):
            engine.top_central("not_a_measure")


# -------------------------------------------------------------------
# Corpus summary
# -------------------------------------------------------------------


class TestCorpusSummary:
    def test_summary_contains_expected_keys(self, engine):
        s = engine.corpus_summary()
        for key in (
            "researchers",
            "edges",
            "publications",
            "main_component_size",
            "main_component_pct",
        ):
            assert key in s

    def test_summary_values_are_positive(self, engine):
        s = engine.corpus_summary()
        assert s["researchers"] > 0
        assert s["publications"] > 0

    def test_main_component_pct_is_between_0_and_100(self, engine):
        s = engine.corpus_summary()
        assert 0 <= s["main_component_pct"] <= 100


class TestMainComponent:
    def test_stiglitz_in_main_component(self, engine):
        # Stiglitz is connected; should be in the largest component
        assert engine.in_main_component("s001")

    def test_myerson_not_in_main_component(self, engine):
        # Myerson is isolated
        assert not engine.in_main_component("m001")

    def test_profile_flags_main_component_membership(self, engine):
        profile = engine.profile("s001")
        assert profile.in_main_component is True
        profile_isolated = engine.profile("m001")
        assert profile_isolated.in_main_component is False

    def test_main_component_researchers_sorted_by_betweenness(self, engine):
        researchers = engine.main_component_researchers()
        scores = [r.centrality.get("betweenness", 0.0) for r in researchers]
        assert scores == sorted(scores, reverse=True)

    def test_main_component_researchers_excludes_isolated(self, engine):
        ids = {r.author_id for r in engine.main_component_researchers()}
        assert "m001" not in ids
