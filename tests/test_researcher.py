"""Tests for the Researcher class.

Reading these tests should tell you what a Researcher is supposed to do:
  - it is uniquely identified by author_id
  - it accumulates paper_ids over time
  - it holds optional metadata (affiliation, h-index, citation count)
  - it serializes to/from JSON cleanly
  - centrality scores are attached after graph computation, not at construction
"""

import pytest
from src.researcher import Researcher


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture
def stiglitz():
    return Researcher(
        author_id="s001",
        name="Joseph Stiglitz",
        affiliation="Columbia University",
        citation_count=120000,
        h_index=80,
    )


@pytest.fixture
def akerlof():
    return Researcher(
        author_id="a001",
        name="George Akerlof",
        affiliation="Georgetown University",
        citation_count=50000,
        h_index=60,
    )


# -------------------------------------------------------------------
# Construction
# -------------------------------------------------------------------

class TestConstruction:
    def test_required_fields_stored(self, stiglitz):
        assert stiglitz.author_id == "s001"
        assert stiglitz.name == "Joseph Stiglitz"

    def test_optional_fields_stored(self, stiglitz):
        assert stiglitz.affiliation == "Columbia University"
        assert stiglitz.citation_count == 120000
        assert stiglitz.h_index == 80

    def test_affiliation_defaults_to_none(self):
        r = Researcher(author_id="x001", name="Anonymous")
        assert r.affiliation is None

    def test_numeric_fields_default_to_zero(self):
        r = Researcher(author_id="x001", name="Anonymous")
        assert r.citation_count == 0
        assert r.h_index == 0

    def test_paper_ids_start_empty(self, stiglitz):
        assert stiglitz.paper_ids == set()

    def test_centrality_starts_empty(self, stiglitz):
        assert stiglitz.centrality == {}

    def test_empty_author_id_raises(self):
        with pytest.raises(ValueError, match="author_id"):
            Researcher(author_id="", name="Someone")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            Researcher(author_id="x001", name="")


# -------------------------------------------------------------------
# Paper accumulation
# -------------------------------------------------------------------

class TestPaperAccumulation:
    def test_add_paper(self, stiglitz):
        stiglitz.add_paper("p001")
        assert "p001" in stiglitz.paper_ids

    def test_add_paper_is_idempotent(self, stiglitz):
        stiglitz.add_paper("p001")
        stiglitz.add_paper("p001")
        assert stiglitz.paper_count_in_corpus == 1

    def test_paper_count_increments(self, stiglitz):
        for i in range(5):
            stiglitz.add_paper(f"p{i:03d}")
        assert stiglitz.paper_count_in_corpus == 5

    def test_paper_count_with_no_papers(self, stiglitz):
        assert stiglitz.paper_count_in_corpus == 0


# -------------------------------------------------------------------
# Centrality
# -------------------------------------------------------------------

class TestCentrality:
    def test_centrality_can_be_set(self, stiglitz):
        stiglitz.centrality = {
            "degree": 0.5,
            "betweenness": 0.3,
            "eigenvector": 0.2,
            "closeness": 0.4,
        }
        assert stiglitz.centrality["betweenness"] == 0.3

    def test_missing_centrality_key_returns_zero_via_get(self, stiglitz):
        # Code elsewhere does r.centrality.get(measure, 0.0) — confirm
        # this is safe even on a fresh researcher.
        assert stiglitz.centrality.get("betweenness", 0.0) == 0.0


# -------------------------------------------------------------------
# Equality and hashing
# -------------------------------------------------------------------

class TestEqualityAndHashing:
    def test_same_author_id_is_equal(self):
        r1 = Researcher(author_id="s001", name="Joseph Stiglitz")
        r2 = Researcher(author_id="s001", name="J. Stiglitz")  # different name
        assert r1 == r2

    def test_different_author_id_is_not_equal(self, stiglitz, akerlof):
        assert stiglitz != akerlof

    def test_researchers_usable_in_set(self, stiglitz, akerlof):
        s = {stiglitz, akerlof}
        assert len(s) == 2

    def test_duplicate_in_set_is_deduped(self):
        r1 = Researcher(author_id="s001", name="Joseph Stiglitz")
        r2 = Researcher(author_id="s001", name="J. Stiglitz")
        s = {r1, r2}
        assert len(s) == 1

    def test_not_equal_to_non_researcher(self, stiglitz):
        assert stiglitz != "s001"
        assert stiglitz != 42


# -------------------------------------------------------------------
# Serialization round-trip
# -------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_contains_required_keys(self, stiglitz):
        d = stiglitz.to_dict()
        for key in ("author_id", "name", "affiliation", "citation_count",
                    "h_index", "paper_ids", "centrality"):
            assert key in d

    def test_round_trip_preserves_basic_fields(self, stiglitz):
        d = stiglitz.to_dict()
        r = Researcher.from_dict(d)
        assert r.author_id == stiglitz.author_id
        assert r.name == stiglitz.name
        assert r.affiliation == stiglitz.affiliation
        assert r.citation_count == stiglitz.citation_count
        assert r.h_index == stiglitz.h_index

    def test_round_trip_preserves_paper_ids(self, stiglitz):
        stiglitz.add_paper("p001")
        stiglitz.add_paper("p002")
        r = Researcher.from_dict(stiglitz.to_dict())
        assert r.paper_ids == {"p001", "p002"}

    def test_round_trip_preserves_centrality(self, stiglitz):
        stiglitz.centrality = {"degree": 0.5, "betweenness": 0.3}
        r = Researcher.from_dict(stiglitz.to_dict())
        assert r.centrality == {"degree": 0.5, "betweenness": 0.3}

    def test_round_trip_with_none_affiliation(self):
        r = Researcher(author_id="x001", name="Anonymous")
        r2 = Researcher.from_dict(r.to_dict())
        assert r2.affiliation is None

    def test_from_dict_tolerates_missing_optional_fields(self):
        minimal = {"author_id": "x001", "name": "Minimal"}
        r = Researcher.from_dict(minimal)
        assert r.citation_count == 0
        assert r.h_index == 0
        assert r.paper_ids == set()
        assert r.centrality == {}

    def test_repr_is_informative(self, stiglitz):
        stiglitz.add_paper("p001")
        r = repr(stiglitz)
        assert "Stiglitz" in r
        assert "papers=1" in r
