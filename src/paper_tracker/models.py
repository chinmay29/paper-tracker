"""Data models for paper metadata."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Paper:
    """Represents an arXiv paper with metadata."""
    
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    published: datetime
    updated: datetime
    pdf_url: str
    arxiv_url: str
    
    # Optional metadata for scoring (Phase 2)
    has_code: bool = False
    github_url: Optional[str] = None
    
    # Semantic Scholar enrichment data
    citation_count: int = 0
    reference_count: int = 0
    influential_citation_count: int = 0
    venue: str = ""
    has_open_pdf: bool = False
    
    # Computed fields
    primary_category: str = field(init=False)
    
    def __post_init__(self):
        self.primary_category = self.categories[0] if self.categories else ""
        # Clean up title and abstract (remove newlines)
        self.title = " ".join(self.title.split())
        self.abstract = " ".join(self.abstract.split())
    
    @property
    def authors_str(self) -> str:
        """Return authors as comma-separated string."""
        if len(self.authors) > 3:
            return f"{', '.join(self.authors[:3])}, et al."
        return ", ".join(self.authors)
    
    @property
    def is_recent(self) -> bool:
        """Check if paper was published in the last 7 days."""
        days_old = (datetime.now() - self.published).days
        return days_old <= 7
    
    @property
    def is_highly_cited(self) -> bool:
        """Check if paper has significant citations (20+ for recent papers)."""
        return self.citation_count >= 20
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": ",".join(self.authors),
            "categories": ",".join(self.categories),
            "published": self.published.isoformat(),
            "updated": self.updated.isoformat(),
            "pdf_url": self.pdf_url,
            "arxiv_url": self.arxiv_url,
            "has_code": self.has_code,
            "github_url": self.github_url,
            "citation_count": self.citation_count,
            "reference_count": self.reference_count,
            "influential_citation_count": self.influential_citation_count,
            "venue": self.venue,
            "has_open_pdf": self.has_open_pdf,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        """Create Paper from dictionary."""
        paper = cls(
            arxiv_id=data["arxiv_id"],
            title=data["title"],
            abstract=data["abstract"],
            authors=data["authors"].split(",") if data["authors"] else [],
            categories=data["categories"].split(",") if data["categories"] else [],
            published=datetime.fromisoformat(data["published"]),
            updated=datetime.fromisoformat(data["updated"]),
            pdf_url=data["pdf_url"],
            arxiv_url=data["arxiv_url"],
            has_code=bool(data.get("has_code", False)),
            github_url=data.get("github_url"),
            citation_count=data.get("citation_count", 0) or 0,
            reference_count=data.get("reference_count", 0) or 0,
            influential_citation_count=data.get("influential_citation_count", 0) or 0,
            venue=data.get("venue", "") or "",
            has_open_pdf=bool(data.get("has_open_pdf", False)),
        )
        return paper
