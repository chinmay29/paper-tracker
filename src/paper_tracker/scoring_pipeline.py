"""Main scoring pipeline for papers."""

from datetime import datetime
from typing import Optional
import logging

from .models import Paper
from .scoring import (
    PaperScore,
    TopicRelevance,
    ProductionReadiness,
    Credibility,
    BenchmarkFlags,
)
from .topic_relevance import compute_topic_relevance
from .production_readiness import compute_production_readiness
from .credibility import compute_credibility
from .benchmark_validation import compute_benchmark_flags

logger = logging.getLogger(__name__)


class ScoringPipeline:
    """
    Main pipeline for scoring papers.
    
    Orchestrates all scoring modules and computes final scores.
    """
    
    def __init__(
        self,
        embedding_store=None,
        papers_with_code_client=None,
        semantic_scholar_client=None,
        use_pdf_text: bool = False,
    ):
        """
        Initialize the scoring pipeline.
        
        Args:
            embedding_store: Optional EmbeddingsStore for semantic similarity
            papers_with_code_client: Optional client for code availability
            semantic_scholar_client: Optional client for author h-indices
            use_pdf_text: If True, download and extract PDF text for scoring
        """
        self.embedding_store = embedding_store
        self.papers_with_code_client = papers_with_code_client
        self.semantic_scholar_client = semantic_scholar_client
        self.use_pdf_text = use_pdf_text
        self._pdf_extractor = None
    
    def _get_pdf_extractor(self):
        """Lazy-load the PDF extractor."""
        if self._pdf_extractor is None and self.use_pdf_text:
            from .pdf_extractor import PDFExtractor
            self._pdf_extractor = PDFExtractor()
        return self._pdf_extractor
    
    def _get_full_text(self, paper: Paper) -> Optional[str]:
        """Get full paper text if PDF extraction is enabled."""
        if not self.use_pdf_text:
            return None
        
        extractor = self._get_pdf_extractor()
        if not extractor:
            return None
        
        try:
            return extractor.get_combined_text(
                arxiv_id=paper.arxiv_id,
                pdf_url=paper.pdf_url,
                title=paper.title,
                abstract=paper.abstract,
            )
        except Exception as e:
            logger.warning(f"Failed to extract PDF text for {paper.arxiv_id}: {e}")
            return None
    
    def score_paper(
        self,
        paper: Paper,
        papers_with_code_result: Optional[dict] = None,
        author_h_indices: Optional[dict[str, int]] = None,
    ) -> PaperScore:
        """
        Score a single paper.
        
        Args:
            paper: Paper to score
            papers_with_code_result: Optional pre-fetched PWC data
            author_h_indices: Optional pre-fetched author h-indices
            
        Returns:
            PaperScore with all component scores
        """
        # Get full text if enabled
        full_text = self._get_full_text(paper)
        
        # 1. Topic relevance
        topic = compute_topic_relevance(paper, self.embedding_store, full_text)
        
        # 2. Production readiness
        production = compute_production_readiness(paper, papers_with_code_result, full_text)
        
        # 3. Credibility
        cred = compute_credibility(paper, author_h_indices)
        
        # 4. Benchmark flags
        flags = compute_benchmark_flags(paper, full_text)
        
        # 5. Calculate days since published
        days_since = (datetime.now() - paper.published).days
        
        # 6. Create score object
        score = PaperScore(
            arxiv_id=paper.arxiv_id,
            topic_relevance=topic,
            production_readiness=production,
            credibility=cred,
            benchmark_flags=flags,
            citation_count=paper.citation_count,
            influential_citation_count=paper.influential_citation_count,
            days_since_published=days_since,
        )
        
        # 7. Compute composite score
        score.compute_composite_score()
        
        return score
    
    def score_papers(
        self,
        papers: list[Paper],
        batch_enrich: bool = False,
    ) -> list[PaperScore]:
        """
        Score multiple papers.
        
        Args:
            papers: List of papers to score
            batch_enrich: If True, batch-fetch external data first
            
        Returns:
            List of PaperScore objects
        """
        # TODO: Implement batch enrichment from external APIs
        # - Papers with Code batch lookup
        # - Semantic Scholar author h-index batch lookup
        
        scores = []
        for paper in papers:
            score = self.score_paper(paper)
            scores.append(score)
        
        return scores
    
    def get_ranked_papers(
        self,
        scores: list[PaperScore],
        min_score: float = 0,
        tier: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[PaperScore]:
        """
        Filter and rank scored papers.
        
        Args:
            scores: List of PaperScore objects
            min_score: Minimum composite score
            tier: Filter by rank tier (S, A, B, C, D)
            category: Filter by topic category
            
        Returns:
            Filtered and sorted list of scores
        """
        filtered = scores
        
        if min_score > 0:
            filtered = [s for s in filtered if s.composite_score >= min_score]
        
        if tier:
            filtered = [s for s in filtered if s.rank_tier == tier.upper()]
        
        if category:
            filtered = [
                s for s in filtered 
                if s.topic_relevance.topic_category == category
            ]
        
        # Sort by composite score descending
        filtered.sort(key=lambda s: s.composite_score, reverse=True)
        
        return filtered


def score_paper(paper: Paper, use_pdf_text: bool = False) -> PaperScore:
    """
    Convenience function to score a single paper.
    
    Args:
        paper: Paper to score
        use_pdf_text: If True, download and analyze full PDF text
        
    Returns:
        PaperScore with all component scores
    """
    pipeline = ScoringPipeline(use_pdf_text=use_pdf_text)
    return pipeline.score_paper(paper)


def score_papers(papers: list[Paper], use_pdf_text: bool = False) -> list[PaperScore]:
    """
    Convenience function to score multiple papers.
    
    Args:
        papers: List of papers to score
        use_pdf_text: If True, download and analyze full PDF text
        
    Returns:
        List of PaperScore objects, sorted by score descending
    """
    pipeline = ScoringPipeline(use_pdf_text=use_pdf_text)
    scores = pipeline.score_papers(papers)
    scores.sort(key=lambda s: s.composite_score, reverse=True)
    return scores
