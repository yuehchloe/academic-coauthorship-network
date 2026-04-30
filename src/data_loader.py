"""
DataLoader — Semantic Scholar API access layer.

Responsibilities:
    1. Search papers by keyword + year range (paper bulk search endpoint).
    2. Batch-fetch full paper metadata including authors.
    3. Batch-fetch author records (affiliation, h-index, citations).
    4. Cache every API response to disk so re-runs don't burn rate limit.
    5. Build a hydrated CollaborationGraph from the pulled data.

Design notes:
    - We separate I/O (this class) from graph logic (CollaborationGraph). The
      graph never makes network calls. The loader never does centrality math.
    - Caching is keyed by query parameters, so changing the query forces a
      re-fetch but reusing the same query is free.
    - Semantic Scholar requires exponential backoff. We do that here so
      callers don't have to think about it.
    - Rate limit (April 2026): 5,000 requests per 5 min shared across
      unauthenticated users, ~1 RPS per authenticated key. We default to
      polite serial requests with backoff.
"""

from __future__ import annotations
import json
import hashlib
import time
import logging
from pathlib import Path
from typing import Optional, Iterable
import urllib.request
import urllib.error
import urllib.parse

from .researcher import Researcher
from .publication import Publication
from .graph import CollaborationGraph


log = logging.getLogger(__name__)


class SemanticScholarError(Exception):
    """Raised when the Semantic Scholar API returns an unrecoverable error."""


class DataLoader:
    """Fetches papers and authors from Semantic Scholar with disk caching.

    Typical use:
        loader = DataLoader(cache_dir="data/cache", api_key=None)
        papers = loader.search_papers("asymmetric information", 2015, 2025, limit=200)
        graph = loader.build_graph(papers)
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    # publicationVenue.name is more consistent than the free-text `venue` field —
    # we request both and prefer publicationVenue.name when available.
    PAPER_FIELDS = (
        "title,year,venue,publicationVenue,citationCount,abstract,"
        "authors.authorId,authors.name,fieldsOfStudy"
    )
    # /paper/{id}/citations and /author/{id}/papers don't accept dotted
    # author subfield syntax. They take 'authors' as a single field and
    # return authorId+name automatically nested inside it.
    PAPER_FIELDS_NO_DOTTED = (
        "title,year,venue,publicationVenue,citationCount,abstract,authors,fieldsOfStudy"
    )
    AUTHOR_FIELDS = "name,affiliations,citationCount,hIndex,paperCount"

    # Conservative defaults. Without an API key, we want to be a good citizen.
    # The shared anonymous rate limit on S2 is 5000 req/5min globally, so
    # we want generous delays and long backoffs. With an API key, callers
    # can override these.
    DEFAULT_REQUEST_DELAY = 1.5  # seconds between requests
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 30.0  # seconds — first retry waits this long

    def __init__(
        self,
        cache_dir: str | Path = "data/cache",
        api_key: Optional[str] = None,
        request_delay: float = DEFAULT_REQUEST_DELAY,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = api_key
        self.request_delay = request_delay
        self._last_request_time: float = 0.0

    # ---------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------

    def search_papers(
        self,
        query: str,
        year_start: int,
        year_end: int,
        limit: int = 200,
        fields_of_study: Optional[list[str]] = None,
        venues: Optional[list[str]] = None,
        venue_allowlist: Optional[list[str]] = None,
    ) -> list[Publication]:
        """Search for papers by keyword, return a list of Publication objects.

        Uses the /paper/search/bulk endpoint. Three layers of filtering are
        available, in increasing strictness:

        Args:
            query: Free-text search query (matched against title + abstract).
            year_start, year_end: Inclusive year range.
            limit: Max results from S2 (cap is 1000 per page).
            fields_of_study: S2 field-of-study tags to require, e.g.
                ["Economics"] or ["Economics", "Business"]. Server-side
                filter; cheap. Recommended for any subject-specific corpus.
            venues: S2 venue strings to require server-side. CAUTION: the
                venue field is free-text on S2 and matching is exact, so
                "American Economic Review" will miss papers tagged "The
                American Economic Review". Prefer venue_allowlist below.
            venue_allowlist: List of venue substrings to keep client-side
                AFTER the server response. Case-insensitive substring match
                against both `venue` and `publicationVenue.name`. More
                forgiving than server-side venue filtering.

        Returns:
            Deduplicated list of Publication objects.
        """
        cache_key = self._cache_key(
            "search",
            query=query,
            year_start=year_start,
            year_end=year_end,
            limit=limit,
            fields_of_study=fields_of_study,
            venues=venues,
            venue_allowlist=venue_allowlist,
        )
        cached = self._load_cache(cache_key)
        if cached is not None:
            log.info("Cache hit: search %r (%d results)", query, len(cached))
            return [Publication.from_dict(p) for p in cached]

        log.info("Cache miss: searching for %r", query)
        params: dict = {
            "query": query,
            "year": f"{year_start}-{year_end}",
            "fields": self.PAPER_FIELDS,
            "limit": min(limit, 1000),
        }
        if fields_of_study:
            params["fieldsOfStudy"] = ",".join(fields_of_study)
        if venues:
            params["venue"] = ",".join(venues)

        url = f"{self.BASE_URL}/paper/search/bulk?{urllib.parse.urlencode(params)}"
        raw = self._get_json(url)

        publications: list[Publication] = []
        seen_ids: set[str] = set()
        kept_by_allowlist = 0
        dropped_by_allowlist = 0
        for item in raw.get("data", []):
            pub = self._paper_dict_to_publication(item)
            if pub is None or pub.paper_id in seen_ids:
                continue

            if venue_allowlist and not self._venue_matches(item, venue_allowlist):
                dropped_by_allowlist += 1
                continue

            publications.append(pub)
            seen_ids.add(pub.paper_id)
            if venue_allowlist:
                kept_by_allowlist += 1

        if venue_allowlist:
            log.info(
                "Venue allowlist: kept %d, dropped %d",
                kept_by_allowlist,
                dropped_by_allowlist,
            )

        self._save_cache(cache_key, [p.to_dict() for p in publications])
        log.info("Fetched %d unique papers for %r", len(publications), query)
        return publications

    @staticmethod
    def _venue_matches(item: dict, allowlist: list[str]) -> bool:
        """Case-insensitive match against both venue strings S2 provides
        for a paper. Uses the per-pattern match modes (exact/prefix/substring)
        defined in venues.py when given a list of (pattern, mode) tuples; falls
        back to substring matching when given a flat list of strings (for
        backward compatibility)."""
        # Determine candidate venue strings.
        candidates: list[str] = []
        if item.get("venue"):
            candidates.append(item["venue"])
        pv = item.get("publicationVenue")
        if pv and isinstance(pv, dict) and pv.get("name"):
            candidates.append(pv["name"])
        if not candidates:
            return False

        # Detect whether the allowlist is the new (pattern, mode) format or
        # the old flat list of substrings.
        if allowlist and isinstance(allowlist[0], tuple):
            # New format: delegate to venue_matches from venues.py
            from .venues import venue_matches

            return any(venue_matches(c, allowlist) for c in candidates)

        # Legacy: flat list of substrings, case-insensitive substring match.
        allow_lower = [a.lower() for a in allowlist]
        cand_lower = [c.lower() for c in candidates]
        return any(a in c for a in allow_lower for c in cand_lower)

    def fetch_authors(self, author_ids: Iterable[str]) -> dict[str, Researcher]:
        """Batch-fetch author records. Returns dict keyed by author_id.

        Uses the /author/batch endpoint which accepts up to 1000 IDs per
        POST request. We dedupe and chunk automatically.
        """
        unique_ids = sorted(set(aid for aid in author_ids if aid))
        if not unique_ids:
            return {}

        cache_key = self._cache_key("authors", ids=unique_ids)
        cached = self._load_cache(cache_key)
        if cached is not None:
            log.info("Cache hit: %d authors", len(cached))
            return {aid: Researcher.from_dict(d) for aid, d in cached.items()}

        log.info("Cache miss: fetching %d authors", len(unique_ids))
        result: dict[str, Researcher] = {}
        for chunk in self._chunked(unique_ids, 500):
            url = f"{self.BASE_URL}/author/batch?fields={self.AUTHOR_FIELDS}"
            raw = self._post_json(url, {"ids": chunk})
            for item in raw:
                if item is None:
                    continue
                researcher = self._author_dict_to_researcher(item)
                if researcher is not None:
                    result[researcher.author_id] = researcher

        # Cache as serializable dicts.
        self._save_cache(
            cache_key,
            {aid: r.to_dict() for aid, r in result.items()},
        )
        return result

    def build_graph(
        self,
        publications: list[Publication],
        fetch_full_authors: bool = True,
    ) -> CollaborationGraph:
        """Construct a CollaborationGraph from a list of publications.

        If fetch_full_authors=True, we also batch-fetch author metadata
        (affiliation, h-index, etc) for all unique authors on these papers.
        Otherwise we just use the names embedded in the paper records.
        """
        graph = CollaborationGraph()

        # Collect all unique author ids across the publications.
        all_author_ids: set[str] = set()
        author_names_from_papers: dict[str, str] = {}
        for pub in publications:
            for aid in pub.author_ids:
                all_author_ids.add(aid)

        if fetch_full_authors:
            researchers = self.fetch_authors(all_author_ids)
        else:
            researchers = {}

        # For any author not returned by the batch endpoint, fall back to
        # the name embedded in the paper record.
        cached_paper_authors = self._extract_authors_from_papers(publications)
        for aid in all_author_ids:
            if aid in researchers:
                graph.add_researcher(researchers[aid])
            elif aid in cached_paper_authors:
                graph.add_researcher(
                    Researcher(author_id=aid, name=cached_paper_authors[aid])
                )
            # else: skip — author has no usable record anywhere

        for pub in publications:
            graph.add_publication(pub)

        return graph

    # ---------------------------------------------------------------
    # Citation-graph expansion methods
    # ---------------------------------------------------------------

    def resolve_author_by_name(
        self,
        name: str,
        prefer_econ: bool = True,
    ) -> Optional[str]:
        """Resolve a display name to an S2 authorId via /author/search.

        S2's author search returns multiple candidates for common names.
        We pick the candidate with the highest paperCount (a crude proxy
        for "most prolific Joe Schmoe"). When prefer_econ=True we further
        filter to candidates whose papers contain at least one venue from
        our econ allowlist — but that's expensive, so we skip it for now
        and rely on paperCount.

        Returns the S2 authorId or None if resolution fails. Cached by name.
        """
        cache_key = self._cache_key("author_resolve", name=name)
        cached = self._load_cache(cache_key)
        if cached is not None:
            log.info("Cache hit: resolve %r -> %r", name, cached)
            return cached if cached else None

        log.info("Cache miss: resolving author %r", name)
        params = {
            "query": name,
            "fields": "name,paperCount,citationCount,hIndex",
            "limit": 10,
        }
        url = f"{self.BASE_URL}/author/search?{urllib.parse.urlencode(params)}"
        try:
            raw = self._get_json(url)
        except SemanticScholarError as e:
            log.warning("Author resolution failed for %r: %s", name, e)
            self._save_cache(cache_key, "")
            return None

        candidates = raw.get("data", []) or []
        if not candidates:
            log.warning("No S2 candidates found for %r", name)
            self._save_cache(cache_key, "")
            return None

        # Pick most-cited candidate. citationCount is a better signal than
        # paperCount for established researchers (Stiglitz has ~200k cites).
        candidates.sort(
            key=lambda c: -(c.get("citationCount") or 0),
        )
        best = candidates[0]
        author_id = best.get("authorId")

        log.info(
            "Resolved %r -> %s (%s, %d citations, %d papers)",
            name,
            author_id,
            best.get("name"),
            best.get("citationCount") or 0,
            best.get("paperCount") or 0,
        )
        self._save_cache(cache_key, author_id or "")
        return author_id

    def fetch_author_papers(
        self,
        author_id: str,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
        limit: int = 1000,
    ) -> list[Publication]:
        """Fetch all papers by a given author.

        Uses /author/{id}/papers. Returns up to `limit` papers, optionally
        filtered to a year range client-side (the endpoint doesn't support
        server-side year filtering as of this writing).
        """
        cache_key = self._cache_key(
            "author_papers",
            author_id=author_id,
            year_start=year_start,
            year_end=year_end,
            limit=limit,
        )
        cached = self._load_cache(cache_key)
        if cached is not None:
            log.info(
                "Cache hit: %d papers for author %s",
                len(cached),
                author_id,
            )
            return [Publication.from_dict(p) for p in cached]

        log.info("Cache miss: fetching papers for author %s", author_id)
        params = {
            "fields": self.PAPER_FIELDS_NO_DOTTED,
            "limit": min(limit, 1000),
        }
        url = (
            f"{self.BASE_URL}/author/{author_id}/papers"
            f"?{urllib.parse.urlencode(params)}"
        )
        raw = self._get_json(url)

        publications: list[Publication] = []
        for item in raw.get("data", []):
            pub = self._paper_dict_to_publication(item)
            if pub is None:
                continue
            if year_start is not None and (pub.year is None or pub.year < year_start):
                continue
            if year_end is not None and (pub.year is None or pub.year > year_end):
                continue
            publications.append(pub)

        self._save_cache(cache_key, [p.to_dict() for p in publications])
        log.info(
            "Fetched %d papers for author %s (after year filter)",
            len(publications),
            author_id,
        )
        return publications

    def fetch_paper_citations(
        self,
        paper_id: str,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
        limit: int = 1000,
    ) -> list[Publication]:
        """Fetch papers that cite the given paper.

        Uses /paper/{id}/citations. The response wraps each citing paper
        in {"citingPaper": {...}}, so we unwrap before parsing.
        """
        cache_key = self._cache_key(
            "paper_citations",
            paper_id=paper_id,
            year_start=year_start,
            year_end=year_end,
            limit=limit,
        )
        cached = self._load_cache(cache_key)
        if cached is not None:
            log.info(
                "Cache hit: %d citations for paper %s",
                len(cached),
                paper_id,
            )
            return [Publication.from_dict(p) for p in cached]

        log.info("Cache miss: fetching citations for paper %s", paper_id)
        params = {
            "fields": self.PAPER_FIELDS_NO_DOTTED,
            "limit": min(limit, 1000),
        }
        url = (
            f"{self.BASE_URL}/paper/{paper_id}/citations"
            f"?{urllib.parse.urlencode(params)}"
        )
        try:
            raw = self._get_json(url)
        except SemanticScholarError as e:
            log.warning("Citations fetch failed for %s: %s", paper_id, e)
            self._save_cache(cache_key, [])
            return []

        publications: list[Publication] = []
        for wrapper in raw.get("data", []):
            citing = wrapper.get("citingPaper")
            if not citing:
                continue
            pub = self._paper_dict_to_publication(citing)
            if pub is None:
                continue
            if year_start is not None and (pub.year is None or pub.year < year_start):
                continue
            if year_end is not None and (pub.year is None or pub.year > year_end):
                continue
            publications.append(pub)

        self._save_cache(cache_key, [p.to_dict() for p in publications])
        log.info(
            "Fetched %d citations for paper %s (after year filter)",
            len(publications),
            paper_id,
        )
        return publications

    # ---------------------------------------------------------------
    # Parsing helpers
    # ---------------------------------------------------------------

    @staticmethod
    def _paper_dict_to_publication(item: dict) -> Optional[Publication]:
        """Convert an S2 /paper/search/bulk response item to a Publication.
        Returns None if the record is too incomplete to use."""
        paper_id = item.get("paperId")
        title = item.get("title")
        if not paper_id or not title:
            return None

        author_ids = []
        for a in item.get("authors", []) or []:
            aid = a.get("authorId")
            if aid:
                author_ids.append(aid)

        # Prefer the structured publicationVenue.name; fall back to free-text venue.
        venue = None
        pv = item.get("publicationVenue")
        if pv and isinstance(pv, dict) and pv.get("name"):
            venue = pv["name"]
        elif item.get("venue"):
            venue = item["venue"]

        return Publication(
            paper_id=paper_id,
            title=title,
            year=item.get("year"),
            author_ids=author_ids,
            venue=venue,
            citation_count=item.get("citationCount") or 0,
            abstract=item.get("abstract"),
        )

    @staticmethod
    def _author_dict_to_researcher(item: dict) -> Optional[Researcher]:
        author_id = item.get("authorId")
        name = item.get("name")
        if not author_id or not name:
            return None

        affiliations = item.get("affiliations") or []
        affiliation = affiliations[0] if affiliations else None

        return Researcher(
            author_id=author_id,
            name=name,
            affiliation=affiliation,
            citation_count=item.get("citationCount") or 0,
            h_index=item.get("hIndex") or 0,
        )

    @staticmethod
    def _extract_authors_from_papers(
        publications: list[Publication],
    ) -> dict[str, str]:
        """Best-effort fallback: pull author names from the paper records
        themselves. Note Publication doesn't store names, only ids — so this
        only works if we wire it through. Currently returns empty; left as
        a hook in case we want to enrich Publication later."""
        return {}

    # ---------------------------------------------------------------
    # HTTP layer with backoff
    # ---------------------------------------------------------------

    def _get_json(self, url: str) -> dict:
        return self._request_with_retry("GET", url)

    def _post_json(self, url: str, body: dict) -> dict:
        return self._request_with_retry("POST", url, body=body)

    def _request_with_retry(
        self,
        method: str,
        url: str,
        body: Optional[dict] = None,
    ) -> dict:
        """Make a request with exponential backoff on rate-limit and
        transient errors. Required by S2's terms of service as of 2025."""
        backoff = self.INITIAL_BACKOFF
        for attempt in range(self.MAX_RETRIES):
            self._respect_rate_limit()
            try:
                return self._do_request(method, url, body)
            except urllib.error.HTTPError as e:
                # Try to read the response body for diagnostic info.
                # S2 typically returns a JSON error message explaining what
                # went wrong (malformed query, unknown field, etc.).
                try:
                    body = e.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    body = "<unable to read response body>"

                # CloudFront sometimes returns 403 instead of 429 when
                # protecting the origin from heavy traffic. Detectable by
                # the HTML "ERROR: The request could not be satisfied"
                # pattern. Treat as retryable.
                cloudfront_throttled = (
                    e.code == 403 and "request could not be satisfied" in body.lower()
                )

                if e.code == 429 or 500 <= e.code < 600 or cloudfront_throttled:
                    reason = (
                        "CloudFront throttling"
                        if cloudfront_throttled
                        else f"HTTP {e.code}"
                    )
                    log.warning(
                        "S2 returned %s (attempt %d/%d), backing off %.1fs. Body: %s",
                        reason,
                        attempt + 1,
                        self.MAX_RETRIES,
                        backoff,
                        body[:200],
                    )
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                # 4xx other than 429/CloudFront-403 = bad request, won't fix itself
                raise SemanticScholarError(
                    f"S2 {method} {url} returned {e.code}: {e.reason}. "
                    f"Response body: {body}"
                ) from e
            except urllib.error.URLError as e:
                log.warning("Network error (attempt %d): %s", attempt + 1, e)
                time.sleep(backoff)
                backoff *= 2
        raise SemanticScholarError(
            f"S2 {method} {url} failed after {self.MAX_RETRIES} attempts"
        )

    def _do_request(
        self,
        method: str,
        url: str,
        body: Optional[dict],
    ) -> dict:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        data: Optional[bytes] = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.monotonic()

    # ---------------------------------------------------------------
    # Cache helpers
    # ---------------------------------------------------------------

    def _cache_key(self, prefix: str, **params) -> str:
        """Hash the parameters into a stable cache filename."""
        canonical = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        return f"{prefix}_{digest}"

    def _cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def _load_cache(self, cache_key: str) -> Optional[object]:
        path = self._cache_path(cache_key)
        if not path.exists():
            return None
        try:
            with path.open() as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Corrupt cache file %s: %s", path, e)
            return None

    def _save_cache(self, cache_key: str, data: object) -> None:
        path = self._cache_path(cache_key)
        with path.open("w") as f:
            json.dump(data, f, indent=2)

    # ---------------------------------------------------------------
    # Misc
    # ---------------------------------------------------------------

    @staticmethod
    def _chunked(items: list, chunk_size: int):
        for i in range(0, len(items), chunk_size):
            yield items[i : i + chunk_size]
