"""Semantic Scholar API client for paper metadata enrichment."""

import time
from typing import Optional

import requests

from .models import Paper


# Semantic Scholar API base URL
S2_API_URL = "https://api.semanticscholar.org/graph/v1"

# Rate limiting: 100 requests per 5 minutes for unauthenticated
MIN_REQUEST_INTERVAL = 0.5  # Conservative rate limit


class SemanticScholarClient:
    """Client for enriching paper data from Semantic Scholar."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the client.
        
        Args:
            api_key: Optional API key for higher rate limits
        """
        self._last_request_time: float = 0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PaperTracker/0.1 (research paper tracking tool)"
        })
        if api_key:
            self.session.headers["x-api-key"] = api_key
    
    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()
    
    def get_paper_by_arxiv_id(
        self,
        arxiv_id: str,
        fields: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """
        Get paper details by arXiv ID.
        
        Args:
            arxiv_id: arXiv paper ID (e.g., "2401.12345")
            fields: List of fields to retrieve
            
        Returns:
            Paper data dict or None if not found
        """
        self._rate_limit()
        
        default_fields = [
            "paperId",
            "title",
            "abstract",
            "citationCount",
            "referenceCount",
            "influentialCitationCount",
            "isOpenAccess",
            "openAccessPdf",
            "year",
            "authors",
            "fieldsOfStudy",
            "publicationTypes",
            "publicationDate",
            "venue",
            "externalIds",
        ]
        
        fields_str = ",".join(fields or default_fields)
        
        try:
            response = self.session.get(
                f"{S2_API_URL}/paper/ARXIV:{arxiv_id}",
                params={"fields": fields_str},
                timeout=30,
            )
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            print(f"Warning: Failed to fetch from S2: {e}")
            return None
    
    def get_papers_batch(
        self,
        arxiv_ids: list[str],
        fields: Optional[list[str]] = None,
    ) -> dict[str, dict]:
        """
        Get details for multiple papers by arXiv IDs.
        
        Args:
            arxiv_ids: List of arXiv paper IDs
            fields: List of fields to retrieve
            
        Returns:
            Dict mapping arxiv_id to paper data
        """
        if not arxiv_ids:
            return {}
        
        self._rate_limit()
        
        default_fields = [
            "paperId",
            "title",
            "citationCount",
            "referenceCount", 
            "influentialCitationCount",
            "isOpenAccess",
            "openAccessPdf",
            "year",
            "venue",
            "externalIds",
        ]
        
        fields_str = ",".join(fields or default_fields)
        
        # Convert to S2 format
        paper_ids = [f"ARXIV:{arxiv_id}" for arxiv_id in arxiv_ids]
        
        # S2 batch limit is 500
        results = {}
        for i in range(0, len(paper_ids), 500):
            batch = paper_ids[i:i + 500]
            
            try:
                response = self.session.post(
                    f"{S2_API_URL}/paper/batch",
                    params={"fields": fields_str},
                    json={"ids": batch},
                    timeout=60,
                )
                response.raise_for_status()
                
                for paper in response.json():
                    if paper and paper.get("externalIds", {}).get("ArXiv"):
                        arxiv_id = paper["externalIds"]["ArXiv"]
                        results[arxiv_id] = paper
                        
            except requests.RequestException as e:
                print(f"Warning: Batch request failed: {e}")
                continue
            
            if i + 500 < len(paper_ids):
                self._rate_limit()
        
        return results
    
    def search_papers(
        self,
        query: str,
        fields_of_study: Optional[list[str]] = None,
        year_range: Optional[tuple[int, int]] = None,
        min_citations: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        Search for papers by query.
        
        Args:
            query: Search query string
            fields_of_study: Filter by fields (e.g., ["Computer Science"])
            year_range: Filter by year range (start, end)
            min_citations: Minimum citation count
            limit: Max results (up to 100)
            offset: Pagination offset
            
        Returns:
            List of paper data dicts
        """
        self._rate_limit()
        
        params = {
            "query": query,
            "limit": min(limit, 100),
            "offset": offset,
            "fields": "paperId,title,abstract,citationCount,year,authors,externalIds,isOpenAccess,venue",
        }
        
        if fields_of_study:
            params["fieldsOfStudy"] = ",".join(fields_of_study)
        
        if year_range:
            params["year"] = f"{year_range[0]}-{year_range[1]}"
        
        if min_citations:
            params["minCitationCount"] = str(min_citations)
        
        try:
            response = self.session.get(
                f"{S2_API_URL}/paper/search",
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
            
        except requests.RequestException as e:
            print(f"Warning: Search failed: {e}")
            return []
    
    def enrich_papers(self, papers: list[Paper]) -> list[Paper]:
        """
        Enrich a list of papers with Semantic Scholar data.
        
        Adds citation counts and other metadata to existing Paper objects.
        
        Args:
            papers: List of Paper objects (with arxiv_id set)
            
        Returns:
            Same list with enriched data
        """
        if not papers:
            return papers
        
        arxiv_ids = [p.arxiv_id for p in papers]
        s2_data = self.get_papers_batch(arxiv_ids)
        
        for paper in papers:
            if paper.arxiv_id in s2_data:
                data = s2_data[paper.arxiv_id]
                paper.citation_count = data.get("citationCount", 0)
                paper.reference_count = data.get("referenceCount", 0)
                paper.influential_citation_count = data.get("influentialCitationCount", 0)
                paper.venue = data.get("venue", "")
                
                # Check for open access PDF
                if data.get("openAccessPdf"):
                    paper.has_open_pdf = True
        
        return papers
