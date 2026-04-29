"""
Publication class — represents a single paper in the corpus.

Publications are NOT graph nodes — researchers are. Publications live as
metadata attached to edges (one paper = potentially many co-authorship edges,
one between every pair of co-authors).
"""

from __future__ import annotations
from typing import Optional


class Publication:
    """A single paper pulled from Semantic Scholar.

    Attributes:
        paper_id: S2 paperId. Primary key.
        title: Paper title.
        year: Publication year.
        author_ids: Ordered list of S2 authorIds for this paper.
        venue: Journal/conference name, or None.
        citation_count: Number of times cited (S2's count).
        abstract: The abstract text, or None. Used by the LLM narrative
            feature; not all papers have abstracts available.
    """

    def __init__(
        self,
        paper_id: str,
        title: str,
        year: Optional[int],
        author_ids: list[str],
        venue: Optional[str] = None,
        citation_count: int = 0,
        abstract: Optional[str] = None,
    ) -> None:
        if not paper_id:
            raise ValueError("paper_id cannot be empty")
        if not title:
            raise ValueError("title cannot be empty")

        self.paper_id: str = paper_id
        self.title: str = title
        self.year: Optional[int] = year
        self.author_ids: list[str] = list(author_ids)
        self.venue: Optional[str] = venue
        self.citation_count: int = citation_count
        self.abstract: Optional[str] = abstract

    @property
    def is_collaborative(self) -> bool:
        """True iff the paper has 2+ authors (only collaborative papers
        contribute edges to the co-authorship graph)."""
        return len(self.author_ids) >= 2

    def coauthor_pairs(self) -> list[tuple[str, str]]:
        """Return every unordered pair of co-authors as (id_a, id_b) tuples
        with id_a < id_b for canonical ordering. Empty list for solo papers."""
        if not self.is_collaborative:
            return []
        ids = sorted(self.author_ids)
        return [
            (ids[i], ids[j])
            for i in range(len(ids))
            for j in range(i + 1, len(ids))
        ]

    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "year": self.year,
            "author_ids": self.author_ids,
            "venue": self.venue,
            "citation_count": self.citation_count,
            "abstract": self.abstract,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Publication":
        return cls(
            paper_id=data["paper_id"],
            title=data["title"],
            year=data.get("year"),
            author_ids=data.get("author_ids", []),
            venue=data.get("venue"),
            citation_count=data.get("citation_count", 0),
            abstract=data.get("abstract"),
        )

    def __repr__(self) -> str:
        year_str = f", {self.year}" if self.year else ""
        return f"Publication({self.title[:40]!r}{year_str}, n_authors={len(self.author_ids)})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Publication):
            return NotImplemented
        return self.paper_id == other.paper_id

    def __hash__(self) -> int:
        return hash(self.paper_id)
