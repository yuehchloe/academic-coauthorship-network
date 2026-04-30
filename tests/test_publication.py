"""Tests for the Publication class.

Reading these tests should tell you what a Publication does:
  - it is uniquely identified by paper_id
  - it knows whether it is collaborative (2+ authors)
  - it can enumerate all unordered co-author pairs (the edges it creates)
  - it serializes to/from JSON cleanly
"""

import pytest
from src.publication import Publication


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture
def solo_paper():
    return Publication(
        paper_id="p001",
        title="Solo Work on Adverse Selection",
        year=2020,
        author_ids=["a001"],
        venue="Econometrica",
        citation_count=10,
    )


@pytest.fixture
def dyad_paper():
    return Publication(
        paper_id="p002",
        title="Signaling Equilibrium",
        year=2021,
        author_ids=["a001", "a002"],
        venue="American Economic Review",
        citation_count=50,
    )


@pytest.fixture
def trio_paper():
    return Publication(
        paper_id="p003",
        title="Three-author Info Design",
        year=2022,
        author_ids=["a001", "a002", "a003"],
        venue="Journal of Economic Theory",
        citation_count=25,
    )


# -------------------------------------------------------------------
# Construction
# -------------------------------------------------------------------

class TestConstruction:
    def test_required_fields_stored(self, dyad_paper):
        assert dyad_paper.paper_id == "p002"
        assert dyad_paper.title == "Signaling Equilibrium"
        assert dyad_paper.year == 2021
        assert dyad_paper.author_ids == ["a001", "a002"]

    def test_optional_fields_stored(self, dyad_paper):
        assert dyad_paper.venue == "American Economic Review"
        assert dyad_paper.citation_count == 50

    def test_venue_defaults_to_none(self):
        p = Publication(paper_id="p001", title="T", year=2020, author_ids=[])
        assert p.venue is None

    def test_abstract_defaults_to_none(self, dyad_paper):
        assert dyad_paper.abstract is None

    def test_abstract_can_be_stored(self):
        p = Publication(
            paper_id="p001", title="T", year=2020,
            author_ids=[], abstract="Some abstract text.",
        )
        assert p.abstract == "Some abstract text."

    def test_empty_paper_id_raises(self):
        with pytest.raises(ValueError, match="paper_id"):
            Publication(paper_id="", title="T", year=2020, author_ids=[])

    def test_empty_title_raises(self):
        with pytest.raises(ValueError, match="title"):
            Publication(paper_id="p001", title="", year=2020, author_ids=[])

    def test_year_can_be_none(self):
        p = Publication(paper_id="p001", title="T", year=None, author_ids=[])
        assert p.year is None

    def test_author_ids_stored_as_list(self, trio_paper):
        assert isinstance(trio_paper.author_ids, list)


# -------------------------------------------------------------------
# Collaborative / coauthor pairs
# -------------------------------------------------------------------

class TestCollaboration:
    def test_solo_paper_is_not_collaborative(self, solo_paper):
        assert not solo_paper.is_collaborative

    def test_dyad_paper_is_collaborative(self, dyad_paper):
        assert dyad_paper.is_collaborative

    def test_trio_paper_is_collaborative(self, trio_paper):
        assert trio_paper.is_collaborative

    def test_zero_author_paper_is_not_collaborative(self):
        p = Publication(paper_id="p001", title="T", year=2020, author_ids=[])
        assert not p.is_collaborative

    def test_solo_paper_has_no_pairs(self, solo_paper):
        assert solo_paper.coauthor_pairs() == []

    def test_zero_author_paper_has_no_pairs(self):
        p = Publication(paper_id="p001", title="T", year=2020, author_ids=[])
        assert p.coauthor_pairs() == []

    def test_dyad_paper_has_one_pair(self, dyad_paper):
        pairs = dyad_paper.coauthor_pairs()
        assert len(pairs) == 1

    def test_trio_paper_has_three_pairs(self, trio_paper):
        pairs = trio_paper.coauthor_pairs()
        assert len(pairs) == 3

    def test_four_author_paper_has_six_pairs(self):
        p = Publication(
            paper_id="p001", title="T", year=2020,
            author_ids=["a1", "a2", "a3", "a4"],
        )
        assert len(p.coauthor_pairs()) == 6

    def test_pairs_are_canonically_ordered(self, dyad_paper):
        # Each pair should have id_a < id_b lexicographically.
        for a, b in dyad_paper.coauthor_pairs():
            assert a < b

    def test_pairs_cover_all_combinations(self, trio_paper):
        # For authors a001, a002, a003, all three pairs should appear.
        pairs = set(trio_paper.coauthor_pairs())
        assert ("a001", "a002") in pairs
        assert ("a001", "a003") in pairs
        assert ("a002", "a003") in pairs

    def test_pairs_have_no_self_loops(self, trio_paper):
        for a, b in trio_paper.coauthor_pairs():
            assert a != b


# -------------------------------------------------------------------
# Equality and hashing
# -------------------------------------------------------------------

class TestEqualityAndHashing:
    def test_same_paper_id_is_equal(self):
        p1 = Publication(paper_id="p001", title="T1", year=2020, author_ids=[])
        p2 = Publication(paper_id="p001", title="T2", year=2021, author_ids=[])
        assert p1 == p2

    def test_different_paper_id_is_not_equal(self, solo_paper, dyad_paper):
        assert solo_paper != dyad_paper

    def test_publications_usable_in_set(self, solo_paper, dyad_paper):
        s = {solo_paper, dyad_paper}
        assert len(s) == 2

    def test_not_equal_to_non_publication(self, solo_paper):
        assert solo_paper != "p001"


# -------------------------------------------------------------------
# Serialization
# -------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_contains_required_keys(self, dyad_paper):
        d = dyad_paper.to_dict()
        for key in ("paper_id", "title", "year", "author_ids",
                    "venue", "citation_count", "abstract"):
            assert key in d

    def test_round_trip_preserves_all_fields(self, trio_paper):
        d = trio_paper.to_dict()
        p = Publication.from_dict(d)
        assert p.paper_id == trio_paper.paper_id
        assert p.title == trio_paper.title
        assert p.year == trio_paper.year
        assert p.author_ids == trio_paper.author_ids
        assert p.venue == trio_paper.venue
        assert p.citation_count == trio_paper.citation_count

    def test_round_trip_preserves_none_fields(self):
        p = Publication(
            paper_id="p001", title="T", year=None,
            author_ids=["a001"], venue=None, abstract=None,
        )
        p2 = Publication.from_dict(p.to_dict())
        assert p2.year is None
        assert p2.venue is None
        assert p2.abstract is None

    def test_round_trip_preserves_coauthor_pairs(self, trio_paper):
        p2 = Publication.from_dict(trio_paper.to_dict())
        assert p2.coauthor_pairs() == trio_paper.coauthor_pairs()

    def test_from_dict_tolerates_missing_optional_fields(self):
        minimal = {"paper_id": "p001", "title": "T", "year": 2020, "author_ids": []}
        p = Publication.from_dict(minimal)
        assert p.citation_count == 0
        assert p.venue is None
        assert p.abstract is None

    def test_repr_is_informative(self, dyad_paper):
        r = repr(dyad_paper)
        assert "Signaling" in r
        assert "n_authors=2" in r
