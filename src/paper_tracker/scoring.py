"""Scoring models and data structures for paper quality assessment."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TopicRelevance:
    """Topic relevance scoring for LLM inference papers."""
    
    score: float  # 0-100
    matched_keywords: list[str] = field(default_factory=list)
    topic_category: str = ""  # Primary topic category
    embedding_similarity: float = 0.0  # Cosine similarity to golden set
    
    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "matched_keywords": self.matched_keywords,
            "topic_category": self.topic_category,
            "embedding_similarity": self.embedding_similarity,
        }


@dataclass
class ProductionReadiness:
    """Production-readiness signals for papers."""
    
    score: float  # 0-100
    has_code: bool = False
    github_url: Optional[str] = None
    has_reproducible_benchmarks: bool = False
    benchmarks_mentioned: list[str] = field(default_factory=list)
    hardware_specified: list[str] = field(default_factory=list)
    tested_at_scale: bool = False
    scale_indicators: list[str] = field(default_factory=list)
    compares_to_baselines: list[str] = field(default_factory=list)
    uses_real_workloads: bool = False
    
    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "has_code": self.has_code,
            "github_url": self.github_url,
            "has_reproducible_benchmarks": self.has_reproducible_benchmarks,
            "benchmarks_mentioned": self.benchmarks_mentioned,
            "hardware_specified": self.hardware_specified,
            "tested_at_scale": self.tested_at_scale,
            "scale_indicators": self.scale_indicators,
            "compares_to_baselines": self.compares_to_baselines,
            "uses_real_workloads": self.uses_real_workloads,
        }


@dataclass
class Credibility:
    """Author and venue credibility scoring."""
    
    score: float  # 0-100
    author_affiliations: list[str] = field(default_factory=list)
    top_tier_affiliations: list[str] = field(default_factory=list)
    max_h_index: int = 0
    venue: str = ""
    venue_tier: str = "preprint"  # "top", "mid", "preprint"
    is_peer_reviewed: bool = False
    
    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "author_affiliations": self.author_affiliations,
            "top_tier_affiliations": self.top_tier_affiliations,
            "max_h_index": self.max_h_index,
            "venue": self.venue,
            "venue_tier": self.venue_tier,
            "is_peer_reviewed": self.is_peer_reviewed,
        }


@dataclass
class BenchmarkFlags:
    """Flags for suspicious or concerning benchmark claims."""
    
    flags: list[str] = field(default_factory=list)
    unrealistic_speedup: bool = False
    speedup_claimed: Optional[float] = None
    outdated_baselines: bool = False
    outdated_baseline_details: list[str] = field(default_factory=list)
    missing_ablations: bool = False
    
    def to_dict(self) -> dict:
        return {
            "flags": self.flags,
            "unrealistic_speedup": self.unrealistic_speedup,
            "speedup_claimed": self.speedup_claimed,
            "outdated_baselines": self.outdated_baselines,
            "outdated_baseline_details": self.outdated_baseline_details,
            "missing_ablations": self.missing_ablations,
        }
    
    @property
    def has_warnings(self) -> bool:
        return len(self.flags) > 0


@dataclass
class PaperScore:
    """Complete scoring result for a paper."""
    
    arxiv_id: str
    topic_relevance: TopicRelevance
    production_readiness: ProductionReadiness
    credibility: Credibility
    benchmark_flags: BenchmarkFlags
    
    # Citation data (from Semantic Scholar)
    citation_count: int = 0
    influential_citation_count: int = 0
    days_since_published: int = 0
    
    # Computed scores
    composite_score: float = 0.0
    rank_tier: str = "D"  # S, A, B, C, D
    scored_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.scored_at is None:
            self.scored_at = datetime.now()
    
    def compute_composite_score(self) -> float:
        """
        Compute weighted composite score.
        
        Weights:
        - Topic Relevance: 25%
        - Production Readiness: 35%
        - Credibility: 25%
        - Citation Bonus: 15% (only for papers >30 days old)
        """
        topic_weight = 0.25
        production_weight = 0.35
        credibility_weight = 0.25
        citation_weight = 0.15
        
        # Base scores
        score = (
            self.topic_relevance.score * topic_weight +
            self.production_readiness.score * production_weight +
            self.credibility.score * credibility_weight
        )
        
        # Citation bonus only for older papers
        if self.days_since_published > 30:
            # Normalize citation score: 100+ citations = max score
            citation_score = min(100, self.citation_count * 1.0)
            score += citation_score * citation_weight
        else:
            # Redistribute weight to other factors for new papers
            redistribution = citation_weight / 3
            score += (
                self.topic_relevance.score * redistribution +
                self.production_readiness.score * redistribution +
                self.credibility.score * redistribution
            )
        
        # Apply penalty for benchmark flags
        if self.benchmark_flags.unrealistic_speedup:
            score *= 0.9  # 10% penalty
        if self.benchmark_flags.outdated_baselines:
            score *= 0.95  # 5% penalty
        
        self.composite_score = min(100, max(0, score))
        self.rank_tier = self._compute_rank_tier()
        return self.composite_score
    
    def _compute_rank_tier(self) -> str:
        """Compute rank tier based on composite score."""
        if self.composite_score >= 85:
            return "S"
        elif self.composite_score >= 70:
            return "A"
        elif self.composite_score >= 50:
            return "B"
        elif self.composite_score >= 30:
            return "C"
        else:
            return "D"
    
    def to_dict(self) -> dict:
        return {
            "arxiv_id": self.arxiv_id,
            "topic_relevance": self.topic_relevance.to_dict(),
            "production_readiness": self.production_readiness.to_dict(),
            "credibility": self.credibility.to_dict(),
            "benchmark_flags": self.benchmark_flags.to_dict(),
            "citation_count": self.citation_count,
            "influential_citation_count": self.influential_citation_count,
            "days_since_published": self.days_since_published,
            "composite_score": self.composite_score,
            "rank_tier": self.rank_tier,
            "scored_at": self.scored_at.isoformat() if self.scored_at else None,
        }
