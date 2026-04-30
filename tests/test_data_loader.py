"""Tests for the DataLoader class.

All tests mock network calls using unittest.mock. No real API calls are
made. These tests document:
  - cache hit/miss behavior
  - parsing of S2 API response shapes (bulk search, author papers, citations)
  - graceful handling of malformed responses
  - venue filter composition
  - the field-syntax bug we fixed (authors.authorId vs authors)
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from src.data_loader import DataLoader, SemanticScholarError
from src.publication import Publication
from src.researcher import Researcher


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture
def loader(tmp_path):
    """A DataLoader with a temporary cache directory."""
    return DataLoader(cache_dir=tmp_path / "cache", request_delay=0.0)


# Sample API response shapes ----------------------------------------

SAMPLE_PAPER = {
    "paperId": "abc123",
    "title": "Optimal Mechanism Design",
    "year": 2021,
    "venue": None,
    "publicationVenue": {"name": "Econometrica"},
    "citationCount": 42,
    "abstract": "We study mechanism design under incomplete information.",
    "authors": [
        {"authorId": "a001", "name": "Joseph Stiglitz"},
        {"authorId": "a002", "name": "Roger Myerson"},
    ],
    "fieldsOfStudy": ["Economics"],
}

SAMPLE_AUTHOR = {
    "authorId": "a001",
    "name": "Joseph Stiglitz",
    "affiliations": ["Columbia University"],
    "citationCount": 120000,
    "hIndex": 80,
    "paperCount": 200,
}

BULK_SEARCH_RESPONSE = {
    "data": [SAMPLE_PAPER],
    "total": 1,
}

AUTHOR_PAPERS_RESPONSE = {
    "data": [SAMPLE_PAPER],
}

CITATIONS_RESPONSE = {
    "data": [
        {"citingPaper": SAMPLE_PAPER},
    ],
}

AUTHOR_SEARCH_RESPONSE = {
    "data": [
        {
            "authorId": "a001",
            "name": "Joseph Stiglitz",
            "citationCount": 120000,
            "paperCount": 200,
        }
    ]
}


# -------------------------------------------------------------------
# Cache behavior
# -------------------------------------------------------------------

class TestCacheBehavior:
    def test_cache_miss_calls_api(self, loader):
        with patch.object(loader, "_do_request", return_value=BULK_SEARCH_RESPONSE):
            papers = loader.search_papers("adverse selection", 2015, 2025, limit=10)
        assert len(papers) == 1

    def test_cache_hit_skips_api(self, loader, tmp_path):
        # Pre-warm the cache by doing a real call...
        with patch.object(loader, "_do_request", return_value=BULK_SEARCH_RESPONSE):
            loader.search_papers("adverse selection", 2015, 2025, limit=10)
        # ...then verify a second call doesn't hit the API
        with patch.object(loader, "_do_request") as mock_req:
            loader.search_papers("adverse selection", 2015, 2025, limit=10)
            mock_req.assert_not_called()

    def test_different_params_different_cache_keys(self, loader):
        with patch.object(loader, "_do_request", return_value=BULK_SEARCH_RESPONSE) as mock:
            loader.search_papers("adverse selection", 2015, 2025, limit=10)
            loader.search_papers("moral hazard", 2015, 2025, limit=10)
            assert mock.call_count == 2

    def test_corrupt_cache_triggers_fresh_fetch(self, loader, tmp_path):
        # Write garbage to the cache file for this query
        cache_key = loader._cache_key(
            "search", query="adverse selection",
            year_start=2015, year_end=2025, limit=10,
            fields_of_study=None, venues=None, venue_allowlist=None,
        )
        cache_file = loader.cache_dir / f"{cache_key}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("this is not json {{{{")

        with patch.object(loader, "_do_request", return_value=BULK_SEARCH_RESPONSE):
            papers = loader.search_papers("adverse selection", 2015, 2025, limit=10)
        assert len(papers) == 1


# -------------------------------------------------------------------
# Parsing — bulk search response
# -------------------------------------------------------------------

class TestBulkSearchParsing:
    def test_returns_publication_objects(self, loader):
        with patch.object(loader, "_do_request", return_value=BULK_SEARCH_RESPONSE):
            papers = loader.search_papers("adverse selection", 2015, 2025)
        assert all(isinstance(p, Publication) for p in papers)

    def test_prefers_publicationvenue_name(self, loader):
        with patch.object(loader, "_do_request", return_value=BULK_SEARCH_RESPONSE):
            papers = loader.search_papers("adverse selection", 2015, 2025)
        # SAMPLE_PAPER has publicationVenue.name = "Econometrica"
        assert papers[0].venue == "Econometrica"

    def test_falls_back_to_free_text_venue(self, loader):
        paper_with_venue = dict(SAMPLE_PAPER, publicationVenue=None, venue="AER")
        response = {"data": [paper_with_venue]}
        with patch.object(loader, "_do_request", return_value=response):
            papers = loader.search_papers("adverse selection", 2015, 2025)
        assert papers[0].venue == "AER"

    def test_deduplication_within_query(self, loader):
        # Two copies of the same paper in the response
        response = {"data": [SAMPLE_PAPER, SAMPLE_PAPER]}
        with patch.object(loader, "_do_request", return_value=response):
            papers = loader.search_papers("adverse selection", 2015, 2025)
        assert len(papers) == 1

    def test_missing_paperid_skipped(self, loader):
        bad = dict(SAMPLE_PAPER, paperId=None)
        response = {"data": [bad, SAMPLE_PAPER]}
        with patch.object(loader, "_do_request", return_value=response):
            papers = loader.search_papers("adverse selection", 2015, 2025)
        assert len(papers) == 1

    def test_missing_title_skipped(self, loader):
        bad = dict(SAMPLE_PAPER, title=None)
        response = {"data": [bad]}
        with patch.object(loader, "_do_request", return_value=response):
            papers = loader.search_papers("adverse selection", 2015, 2025)
        assert len(papers) == 0

    def test_author_ids_extracted(self, loader):
        with patch.object(loader, "_do_request", return_value=BULK_SEARCH_RESPONSE):
            papers = loader.search_papers("adverse selection", 2015, 2025)
        assert "a001" in papers[0].author_ids
        assert "a002" in papers[0].author_ids


# -------------------------------------------------------------------
# Parsing — author papers endpoint (uses PAPER_FIELDS_NO_DOTTED)
# -------------------------------------------------------------------

class TestAuthorPapersParsing:
    def test_returns_publications(self, loader):
        with patch.object(loader, "_do_request", return_value=AUTHOR_PAPERS_RESPONSE):
            papers = loader.fetch_author_papers("a001")
        assert len(papers) == 1
        assert isinstance(papers[0], Publication)

    def test_year_filter_applied(self, loader):
        response = {"data": [SAMPLE_PAPER]}   # year 2021
        with patch.object(loader, "_do_request", return_value=response):
            papers = loader.fetch_author_papers("a001", year_start=2022, year_end=2025)
        assert len(papers) == 0

    def test_year_filter_keeps_in_range(self, loader):
        response = {"data": [SAMPLE_PAPER]}   # year 2021
        with patch.object(loader, "_do_request", return_value=response):
            papers = loader.fetch_author_papers("a001", year_start=2020, year_end=2022)
        assert len(papers) == 1


# -------------------------------------------------------------------
# Parsing — citations endpoint (uses PAPER_FIELDS_NO_DOTTED)
# This is where the authors.authorId vs authors field-syntax bug lived.
# -------------------------------------------------------------------

class TestCitationsParsing:
    def test_returns_publications(self, loader):
        with patch.object(loader, "_do_request", return_value=CITATIONS_RESPONSE):
            pubs = loader.fetch_paper_citations("abc123")
        assert len(pubs) == 1
        assert isinstance(pubs[0], Publication)

    def test_unwraps_citing_paper_key(self, loader):
        # The citations endpoint wraps each paper in {"citingPaper": {...}}.
        # Confirm the parser correctly unwraps it.
        with patch.object(loader, "_do_request", return_value=CITATIONS_RESPONSE):
            pubs = loader.fetch_paper_citations("abc123")
        assert pubs[0].paper_id == "abc123"

    def test_missing_citing_paper_key_skipped(self, loader):
        response = {"data": [{"citingPaper": None}, {"citingPaper": SAMPLE_PAPER}]}
        with patch.object(loader, "_do_request", return_value=response):
            pubs = loader.fetch_paper_citations("abc123")
        assert len(pubs) == 1

    def test_api_error_returns_empty_list(self, loader):
        # fetch_paper_citations catches SemanticScholarError and returns []
        with patch.object(loader, "_do_request", side_effect=SemanticScholarError("boom")):
            pubs = loader.fetch_paper_citations("abc123")
        assert pubs == []


# -------------------------------------------------------------------
# Author resolution
# -------------------------------------------------------------------

class TestAuthorResolution:
    def test_resolves_to_author_id(self, loader):
        with patch.object(loader, "_do_request", return_value=AUTHOR_SEARCH_RESPONSE):
            aid = loader.resolve_author_by_name("Joseph Stiglitz")
        assert aid == "a001"

    def test_picks_most_cited_candidate(self, loader):
        response = {
            "data": [
                {"authorId": "x001", "name": "J. Stiglitz", "citationCount": 100},
                {"authorId": "a001", "name": "Joseph Stiglitz", "citationCount": 120000},
            ]
        }
        with patch.object(loader, "_do_request", return_value=response):
            aid = loader.resolve_author_by_name("Joseph Stiglitz")
        assert aid == "a001"

    def test_no_candidates_returns_none(self, loader):
        with patch.object(loader, "_do_request", return_value={"data": []}):
            aid = loader.resolve_author_by_name("Unknown Person")
        assert aid is None

    def test_api_error_returns_none(self, loader):
        with patch.object(loader, "_do_request", side_effect=SemanticScholarError("fail")):
            aid = loader.resolve_author_by_name("Joseph Stiglitz")
        assert aid is None


# -------------------------------------------------------------------
# Retry / backoff behavior
# -------------------------------------------------------------------

class TestRetryBehavior:
    def test_retries_on_429(self, loader):
        import urllib.error
        http_429 = urllib.error.HTTPError(
            url="", code=429, msg="Too Many Requests",
            hdrs=None, fp=None,
        )
        # Fail twice with 429, then succeed
        with patch.object(loader, "_do_request",
                          side_effect=[http_429, http_429, BULK_SEARCH_RESPONSE]):
            with patch("time.sleep"):  # don't actually wait
                papers = loader.search_papers("test", 2015, 2025)
        assert len(papers) == 1

    def test_raises_after_max_retries(self, loader):
        import urllib.error
        http_429 = urllib.error.HTTPError(
            url="", code=429, msg="Too Many Requests",
            hdrs=None, fp=None,
        )
        with patch.object(loader, "_do_request", side_effect=http_429):
            with patch("time.sleep"):
                with pytest.raises(SemanticScholarError):
                    loader.search_papers("test", 2015, 2025)

    def test_non_retryable_4xx_raises_immediately(self, loader):
        import urllib.error
        http_400 = urllib.error.HTTPError(
            url="", code=400, msg="Bad Request",
            hdrs=None, fp=None,
        )
        with patch.object(loader, "_do_request", side_effect=http_400):
            with patch("time.sleep"):
                with pytest.raises(SemanticScholarError):
                    loader.search_papers("test", 2015, 2025)


# -------------------------------------------------------------------
# Venue filter composition in search_papers
# -------------------------------------------------------------------

class TestVenueFilterInSearch:
    def test_venue_allowlist_drops_non_matching(self, loader):
        response = {
            "data": [
                SAMPLE_PAPER,   # venue: Econometrica — should keep
                dict(SAMPLE_PAPER, paperId="other",
                     publicationVenue={"name": "Nature"}),   # should drop
            ]
        }
        from src.venues import TOP_ECON_VENUE_PATTERNS
        with patch.object(loader, "_do_request", return_value=response):
            papers = loader.search_papers(
                "test", 2015, 2025,
                venue_allowlist=TOP_ECON_VENUE_PATTERNS,
            )
        assert len(papers) == 1
        assert papers[0].venue == "Econometrica"

    def test_no_allowlist_keeps_all(self, loader):
        response = {
            "data": [
                SAMPLE_PAPER,
                dict(SAMPLE_PAPER, paperId="other",
                     publicationVenue={"name": "Nature"}),
            ]
        }
        with patch.object(loader, "_do_request", return_value=response):
            papers = loader.search_papers("test", 2015, 2025)
        assert len(papers) == 2
