"""
Researcher class — represents an individual author in the co-authorship network.

A Researcher is a node in the CollaborationGraph. It holds metadata pulled
from Semantic Scholar plus computed centrality scores that get attached after
the graph is built.
"""

from __future__ import annotations
from typing import Optional


class Researcher:
    """A single author in the information-economics co-authorship network.

    Attributes:
        author_id: Semantic Scholar's stable authorId. The primary key.
        name: Display name as given by the API.
        affiliation: Most recent affiliation string, or None if missing.
        paper_ids: Set of S2 paperIds this author has co-authored within
            our pulled corpus. Not the author's full publication list —
            only what's in scope for this project.
        citation_count: Total citations across the author's S2 record
            (not just within-corpus citations).
        h_index: Author-level h-index from S2.
        centrality: Dict of centrality measures, populated by
            CollaborationGraph.compute_centrality(). Keys: 'degree',
            'betweenness', 'eigenvector', 'closeness'. Empty until computed.
    """

    def __init__(
        self,
        author_id: str,
        name: str,
        affiliation: Optional[str] = None,
        citation_count: int = 0,
        h_index: int = 0,
    ) -> None:
        if not author_id:
            raise ValueError("author_id cannot be empty")
        if not name:
            raise ValueError("name cannot be empty")

        self.author_id: str = author_id
        self.name: str = name
        self.affiliation: Optional[str] = affiliation
        self.citation_count: int = citation_count
        self.h_index: int = h_index
        self.paper_ids: set[str] = set()
        self.centrality: dict[str, float] = {}

    def add_paper(self, paper_id: str) -> None:
        """Record that this researcher co-authored a given paper."""
        self.paper_ids.add(paper_id)

    @property
    def paper_count_in_corpus(self) -> int:
        """How many of this researcher's papers are in our pulled corpus."""
        return len(self.paper_ids)

    def to_dict(self) -> dict:
        """Serialize for JSON persistence and Streamlit display."""
        return {
            "author_id": self.author_id,
            "name": self.name,
            "affiliation": self.affiliation,
            "citation_count": self.citation_count,
            "h_index": self.h_index,
            "paper_ids": sorted(self.paper_ids),
            "centrality": self.centrality,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Researcher":
        """Rehydrate from JSON cache."""
        r = cls(
            author_id=data["author_id"],
            name=data["name"],
            affiliation=data.get("affiliation"),
            citation_count=data.get("citation_count", 0),
            h_index=data.get("h_index", 0),
        )
        r.paper_ids = set(data.get("paper_ids", []))
        r.centrality = data.get("centrality", {})
        return r

    def __repr__(self) -> str:
        return f"Researcher({self.name!r}, papers={self.paper_count_in_corpus})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Researcher):
            return NotImplemented
        return self.author_id == other.author_id

    def __hash__(self) -> int:
        return hash(self.author_id)
