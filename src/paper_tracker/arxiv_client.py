"""arXiv API client for fetching LLM inference papers."""

import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import feedparser
import requests

from .models import Paper


# arXiv API base URL
ARXIV_API_URL = "http://export.arxiv.org/api/query"

# Rate limiting: arXiv requests max 1 request per 3 seconds
MIN_REQUEST_INTERVAL = 3.0

# Categories relevant to LLM inference
LLM_CATEGORIES = ["cs.LG", "cs.CL", "cs.DC", "cs.PF", "cs.AI"]

# Keywords for filtering LLM inference papers
LLM_INFERENCE_KEYWORDS = [
    "inference",
    "serving",
    "optimization",
    "quantization",
    "speculative decoding",
    "KV cache",
    "batching",
    "parallelism",
    "memory optimization",
    "large language model",
    "LLM",
    "transformer",
    "vLLM",
    "TensorRT",
    "attention",
    "throughput",
    "latency",
]


class ArxivClient:
    """Client for fetching papers from arXiv API."""
    
    def __init__(self):
        self._last_request_time: float = 0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PaperTracker/0.1 (research paper tracking tool)"
        })
    
    def _rate_limit(self):
        """Ensure we don't exceed arXiv rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()
    
    def _build_query(
        self,
        keywords: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
    ) -> str:
        """Build arXiv search query string."""
        parts = []
        
        # Add category filter
        cats = categories or LLM_CATEGORIES
        cat_query = " OR ".join(f"cat:{cat}" for cat in cats)
        parts.append(f"({cat_query})")
        
        # Add keyword filter if specified
        if keywords:
            kw_query = " OR ".join(f'all:"{kw}"' for kw in keywords)
            parts.append(f"({kw_query})")
        
        return " AND ".join(parts)
    
    def _parse_entry(self, entry: dict) -> Paper:
        """Parse a feedparser entry into a Paper object."""
        # Extract arXiv ID from the entry id URL
        # Format: http://arxiv.org/abs/2401.12345v1
        arxiv_id = entry.id.split("/abs/")[-1]
        
        # Remove version suffix if present
        if "v" in arxiv_id:
            arxiv_id = arxiv_id.rsplit("v", 1)[0]
        
        # Parse authors
        authors = [author.get("name", "") for author in entry.get("authors", [])]
        
        # Parse categories
        categories = [tag.get("term", "") for tag in entry.get("tags", [])]
        
        # Parse dates
        published = datetime.fromisoformat(
            entry.published.replace("Z", "+00:00")
        ).replace(tzinfo=None)
        updated = datetime.fromisoformat(
            entry.updated.replace("Z", "+00:00")
        ).replace(tzinfo=None)
        
        # Find PDF link
        pdf_url = ""
        arxiv_url = entry.link
        for link in entry.get("links", []):
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href", "")
                break
        
        return Paper(
            arxiv_id=arxiv_id,
            title=entry.title,
            abstract=entry.summary,
            authors=authors,
            categories=categories,
            published=published,
            updated=updated,
            pdf_url=pdf_url,
            arxiv_url=arxiv_url,
        )
    
    def search(
        self,
        query: Optional[str] = None,
        keywords: Optional[list[str]] = None,
        categories: Optional[list[str]] = None,
        max_results: int = 100,
        start: int = 0,
    ) -> list[Paper]:
        """
        Search arXiv for papers.
        
        Args:
            query: Raw query string (overrides keywords/categories if provided)
            keywords: List of keywords to search for
            categories: List of arXiv categories to filter
            max_results: Maximum number of results to return
            start: Starting index for pagination
            
        Returns:
            List of Paper objects
        """
        self._rate_limit()
        
        # Build query
        if query:
            search_query = query
        else:
            search_query = self._build_query(keywords, categories)
        
        # Make API request
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        
        url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        
        # Parse response
        feed = feedparser.parse(response.content)
        
        papers = []
        for entry in feed.entries:
            try:
                paper = self._parse_entry(entry)
                papers.append(paper)
            except Exception as e:
                # Skip malformed entries
                print(f"Warning: Failed to parse entry: {e}")
                continue
        
        return papers
    
    def fetch_llm_inference_papers(
        self,
        days_back: int = 7,
        max_results: int = 200,
        keywords: Optional[list[str]] = None,
    ) -> list[Paper]:
        """
        Fetch recent papers related to LLM inference.
        
        Args:
            days_back: Number of days to look back
            max_results: Maximum number of results
            keywords: Custom keywords to search for (uses defaults if None)
            
        Returns:
            List of Paper objects filtered by date
        """
        # Use custom keywords or default high-signal keywords
        if keywords:
            search_keywords = keywords
        else:
            search_keywords = [
                "inference optimization",
                "LLM serving",
                "quantization",
                "speculative decoding",
                "KV cache",
                "transformer optimization",
                "large language model",
            ]
        
        papers = self.search(
            keywords=search_keywords,
            categories=LLM_CATEGORIES,
            max_results=max_results,
        )
        
        # Filter by date
        cutoff = datetime.now() - timedelta(days=days_back)
        recent_papers = [p for p in papers if p.published >= cutoff]
        
        return recent_papers
    
    def fetch_by_category(
        self,
        category: str,
        days_back: int = 7,
        max_results: int = 100,
    ) -> list[Paper]:
        """Fetch recent papers from a specific category."""
        query = f"cat:{category}"
        papers = self.search(query=query, max_results=max_results)
        
        cutoff = datetime.now() - timedelta(days=days_back)
        return [p for p in papers if p.published >= cutoff]
