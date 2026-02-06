"""FastAPI server for paper tracker web interface."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import Database
from .arxiv_client import ArxivClient
from .semantic_scholar_client import SemanticScholarClient

# Try to import embeddings (optional dependency)
try:
    from .embeddings import EmbeddingsStore, CHROMADB_AVAILABLE
except ImportError:
    CHROMADB_AVAILABLE = False
    EmbeddingsStore = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
db: Database = None
embeddings_store: Optional[EmbeddingsStore] = None

# Global task state for progress tracking
class TaskState:
    def __init__(self):
        self.active = False
        self.total = 0
        self.processed = 0
        self.message = ""
        self.type = "none"  # "scoring", "fetching"

task_state = TaskState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and embeddings on startup."""
    global db, embeddings_store
    
    db = Database()
    logger.info("Database initialized")
    
    if CHROMADB_AVAILABLE and EmbeddingsStore:
        try:
            embeddings_store = EmbeddingsStore()
            # Sync papers from database to embeddings
            embeddings_store.sync_from_database(db)
            logger.info(f"Embeddings store initialized with {embeddings_store.get_count()} papers")
        except Exception as e:
            logger.warning(f"Failed to initialize embeddings store: {e}")
            embeddings_store = None
    else:
        logger.warning("ChromaDB not available - semantic search disabled")
    
    yield
    
    logger.info("Shutting down")


app = FastAPI(
    title="Paper Tracker API",
    description="API for tracking and searching LLM inference research papers",
    version="0.1.0",
    lifespan=lifespan
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5180", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5180"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for API responses
class PaperResponse(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    authors_str: str
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    pdf_url: str
    arxiv_url: str
    has_code: bool
    github_url: Optional[str]
    citation_count: int
    reference_count: int
    influential_citation_count: int
    venue: str
    
    class Config:
        from_attributes = True


class PaperListResponse(BaseModel):
    papers: list[PaperResponse]
    total: int
    page: int
    limit: int


class SearchResponse(BaseModel):
    papers: list[PaperResponse]
    query: str
    mode: str  # "keyword" or "semantic"
    total: int


class StatsResponse(BaseModel):
    total_papers: int
    scored_papers: int
    papers_last_7_days: int
    top_categories: list[tuple[str, int]]
    embeddings_count: Optional[int]
    semantic_search_available: bool


class FetchRequest(BaseModel):
    days: int = 7
    max_results: int = 100
    enrich: bool = False
    keywords: Optional[list[str]] = None  # Custom keywords to search for


class FetchResponse(BaseModel):
    fetched: int
    new_papers: int
    duplicates: int
    message: str


def paper_to_response(paper) -> PaperResponse:
    """Convert Paper model to response model."""
    return PaperResponse(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        abstract=paper.abstract,
        authors=paper.authors,
        authors_str=paper.authors_str,
        categories=paper.categories,
        primary_category=paper.primary_category,
        published=paper.published.isoformat(),
        updated=paper.updated.isoformat(),
        pdf_url=paper.pdf_url,
        arxiv_url=paper.arxiv_url,
        has_code=paper.has_code,
        github_url=paper.github_url,
        citation_count=paper.citation_count,
        reference_count=paper.reference_count,
        influential_citation_count=paper.influential_citation_count,
        venue=paper.venue,
    )


@app.get("/api/papers", response_model=PaperListResponse)
async def list_papers(
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    days: Optional[int] = Query(None, ge=1),
    category: Optional[str] = None,
    sort_by: str = Query("published", pattern="^(published|citations)$"),
):
    """List papers with pagination and optional filters."""
    offset = (page - 1) * limit
    papers = db.list_papers(limit=limit, offset=offset, since_days=days, category=category)
    
    if sort_by == "citations":
        papers = sorted(papers, key=lambda p: p.citation_count, reverse=True)
    
    # Get total count for pagination
    stats = db.get_stats()
    total = stats["total_papers"]
    
    return PaperListResponse(
        papers=[paper_to_response(p) for p in papers],
        total=total,
        page=page,
        limit=limit,
    )


@app.get("/api/papers/{arxiv_id}", response_model=PaperResponse)
async def get_paper(arxiv_id: str):
    """Get a specific paper by arXiv ID."""
    paper = db.get_paper(arxiv_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
    return paper_to_response(paper)


@app.get("/api/search", response_model=SearchResponse)
async def search_papers(
    q: str = Query(..., min_length=1),
    mode: str = Query("keyword", pattern="^(keyword|semantic)$"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Search papers by keyword or semantic similarity.
    
    - **keyword**: Traditional text search in title/abstract
    - **semantic**: Vector similarity search using embeddings
    """
    if mode == "semantic":
        if not embeddings_store:
            raise HTTPException(
                status_code=503, 
                detail="Semantic search not available. Install chromadb."
            )
        
        # Semantic search returns (arxiv_id, score) tuples
        results = embeddings_store.search(q, limit=limit)
        papers = []
        for arxiv_id, score in results:
            paper = db.get_paper(arxiv_id)
            if paper:
                papers.append(paper)
        
        return SearchResponse(
            papers=[paper_to_response(p) for p in papers],
            query=q,
            mode="semantic",
            total=len(papers),
        )
    else:
        # Keyword search
        papers = db.search_papers(q, limit=limit)
        return SearchResponse(
            papers=[paper_to_response(p) for p in papers],
            query=q,
            mode="keyword",
            total=len(papers),
        )


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """Get database and embeddings statistics."""
    stats = db.get_stats()
    return StatsResponse(
        total_papers=stats["total_papers"],
        scored_papers=stats.get("scored_papers", 0),
        papers_last_7_days=stats["papers_last_7_days"],
        top_categories=stats["top_categories"],
        embeddings_count=embeddings_store.get_count() if embeddings_store else None,
        semantic_search_available=embeddings_store is not None,
    )


def _fetch_papers_task(days: int, max_results: int, enrich: bool, keywords: Optional[list[str]] = None):
    """Background task to fetch papers from arXiv."""
    global db, embeddings_store
    
    client = ArxivClient()
    papers = client.fetch_llm_inference_papers(
        days_back=days,
        max_results=max_results,
        keywords=keywords,
    )
    
    if enrich:
        s2_client = SemanticScholarClient()
        papers = s2_client.enrich_papers(papers)
    
    new_count, dup_count = db.insert_papers(papers)
    
    # Sync to embeddings
    if embeddings_store:
        embeddings_store.sync_from_database(db)
    
    logger.info(f"Fetched {len(papers)} papers, {new_count} new, {dup_count} duplicates")


@app.post("/api/fetch", response_model=FetchResponse)
async def fetch_papers(request: FetchRequest, background_tasks: BackgroundTasks):
    """
    Trigger fetching new papers from arXiv.
    
    This runs in the background and returns immediately.
    
    Optionally provide specific keywords to search for. If not provided,
    uses default LLM inference keywords.
    """
    background_tasks.add_task(
        _fetch_papers_task,
        request.days,
        request.max_results,
        request.enrich,
        request.keywords,
    )
    
    keyword_msg = f" with keywords: {request.keywords}" if request.keywords else ""
    
    return FetchResponse(
        fetched=0,
        new_papers=0,
        duplicates=0,
        message=f"Fetching papers from the last {request.days} days{keyword_msg} in background...",
    )


@app.post("/api/sync-embeddings")
async def sync_embeddings():
    """Sync all papers from database to embeddings store."""
    if not embeddings_store:
        raise HTTPException(status_code=503, detail="Embeddings store not available")
    
    count = embeddings_store.sync_from_database(db, limit=5000)
    return {"synced": count, "total": embeddings_store.get_count()}


@app.get("/api/fetch-keywords")
async def get_fetch_keywords():
    """Get available keywords for paper fetching."""
    from .arxiv_client import LLM_INFERENCE_KEYWORDS
    
    # Default keywords used when none specified
    default_keywords = [
        "inference optimization",
        "LLM serving",
        "quantization",
        "speculative decoding",
        "KV cache",
        "transformer optimization",
        "large language model",
    ]
    
    return {
        "default": default_keywords,
        "all": LLM_INFERENCE_KEYWORDS,
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": db is not None,
        "embeddings": embeddings_store is not None,
    }


# ============================================================
# Phase 2: Scoring Endpoints
# ============================================================

from .scoring_pipeline import score_paper, score_papers, ScoringPipeline
import json


class ScoringResponse(BaseModel):
    """Response model for paper scoring."""
    arxiv_id: str
    topic_score: float
    topic_category: str
    production_score: float
    credibility_score: float
    composite_score: float
    rank_tier: str
    benchmark_flags: list[str]
    matched_keywords: list[str]
    has_code: bool
    hardware_specified: list[str]
    top_tier_affiliations: list[str]


class RankedPaperResponse(BaseModel):
    """Paper response with scoring data."""
    arxiv_id: str
    title: str
    abstract: str
    authors_str: str
    published: str
    pdf_url: str
    arxiv_url: str
    composite_score: float
    rank_tier: str
    topic_category: str
    topic_score: float
    production_score: float
    credibility_score: float
    has_code: bool
    benchmark_flags: list[str]


class ScoreAllResponse(BaseModel):
    """Response for batch scoring."""
    scored: int
    total: int
    tier_distribution: dict[str, int]


@app.post("/api/score/{arxiv_id}", response_model=ScoringResponse)
async def score_single_paper(
    arxiv_id: str,
    use_pdf: bool = Query(False, description="Download and analyze full PDF text")
):
    """
    Score a single paper by arXiv ID.
    
    Computes topic relevance, production readiness, credibility,
    and benchmark validation scores.
    
    Set use_pdf=true to download and analyze full paper text (slower but more accurate).
    """
    paper = db.get_paper(arxiv_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
    
    # Score the paper
    result = score_paper(paper, use_pdf_text=use_pdf)
    
    # Save to database
    db.save_paper_score(
        arxiv_id=paper.arxiv_id,
        topic_score=result.topic_relevance.score,
        topic_category=result.topic_relevance.topic_category,
        production_score=result.production_readiness.score,
        credibility_score=result.credibility.score,
        composite_score=result.composite_score,
        rank_tier=result.rank_tier,
        benchmark_flags=json.dumps(result.benchmark_flags.flags),
    )
    
    return ScoringResponse(
        arxiv_id=paper.arxiv_id,
        topic_score=result.topic_relevance.score,
        topic_category=result.topic_relevance.topic_category,
        production_score=result.production_readiness.score,
        credibility_score=result.credibility.score,
        composite_score=result.composite_score,
        rank_tier=result.rank_tier,
        benchmark_flags=result.benchmark_flags.flags,
        matched_keywords=result.topic_relevance.matched_keywords,
        has_code=result.production_readiness.has_code,
        hardware_specified=result.production_readiness.hardware_specified,
        top_tier_affiliations=result.credibility.top_tier_affiliations,
    )


def _score_papers_task(papers: list[Paper], use_pdf: bool = False):
    """Background task to score papers."""
    global db, task_state
    
    logger.info(f"Starting background scoring for {len(papers)} papers (PDF={use_pdf})")
    
    task_state.active = True
    task_state.type = "scoring"
    task_state.total = len(papers)
    task_state.processed = 0
    task_state.message = "Starting scoring..."
    
    for i, paper in enumerate(papers):
        try:
            task_state.message = f"Scoring {paper.arxiv_id}..."
            
            # Check if text is extracted first to avoid re-downloading if possible
            # But score_paper handles that via caching
            
            result = score_paper(paper, use_pdf_text=use_pdf)
            db.save_paper_score(
                arxiv_id=paper.arxiv_id,
                topic_score=result.topic_relevance.score,
                topic_category=result.topic_relevance.topic_category,
                production_score=result.production_readiness.score,
                credibility_score=result.credibility.score,
                composite_score=result.composite_score,
                rank_tier=result.rank_tier,
                benchmark_flags=json.dumps(result.benchmark_flags.flags),
            )
            
            task_state.processed += 1
            
            # Small sleep to prevent freezing the server completely if CPU bound
            if i % 5 == 0:
                import time
                time.sleep(0.1)
                
        except Exception as e:
            logger.warning(f"Failed to score paper {paper.arxiv_id}: {e}")
            # Still increment processed count so progress bar continues
            task_state.processed += 1
            
    logger.info(f"Finished background scoring {len(papers)} papers")
    task_state.active = False
    task_state.message = "Scoring completed"
    task_state.type = "none"  # Reset type so frontend knows it's done


@app.get("/api/task-status")
async def get_task_status():
    """Get status of current background task."""
    return {
        "active": task_state.active,
        "type": task_state.type,
        "total": task_state.total,
        "processed": task_state.processed,
        "message": task_state.message,
    }


@app.post("/api/score-all", response_model=ScoreAllResponse)
async def score_all_papers(
    limit: int = Query(100, ge=1, le=5000),
    use_pdf: bool = Query(False, description="Use PDF text extraction (slower but more accurate)"),
    rescore_all: bool = Query(False, description="Re-score all papers, not just unscored ones"),
    background_tasks: BackgroundTasks = None,
):
    """
    Score papers in batch.
    
    - Default: scores only unscored papers
    - rescore_all=true: re-scores all papers (useful after algorithm updates)
    - use_pdf=true: downloads and analyzes full PDF text (slower but more accurate)
    
    Runs in BACKGROUND. Returns immediately with the number of papers queued.
    """
    # Get papers to score
    if rescore_all:
        papers = db.list_papers(limit=limit)
    else:
        papers = db.get_unscored_papers(limit=limit)
    
    if not papers:
        stats = db.get_stats()
        return ScoreAllResponse(
            scored=0,
            total=stats["scored_papers"],
            tier_distribution=stats.get("tier_distribution", {}),
        )
    
    # Add to background tasks
    if background_tasks:
        background_tasks.add_task(_score_papers_task, papers, use_pdf)
    
    stats = db.get_stats()
    return ScoreAllResponse(
        scored=len(papers),  # Return number of papers queued
        total=stats["scored_papers"],
        tier_distribution=stats.get("tier_distribution", {}),
    )


@app.get("/api/ranked-papers", response_model=list[RankedPaperResponse])
async def get_ranked_papers(
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    min_score: float = Query(0, ge=0, le=100),
    tier: Optional[str] = Query(None, pattern="^[SABCD]$"),
    topic_category: Optional[str] = None,
):
    """
    Get papers ranked by composite score.
    
    Filters:
    - **min_score**: Minimum composite score (0-100)
    - **tier**: Filter by rank tier (S, A, B, C, D)
    - **topic_category**: Filter by topic (quantization, kv_cache, etc.)
    """
    offset = (page - 1) * limit
    
    papers = db.list_papers_ranked(
        limit=limit,
        offset=offset,
        min_score=min_score,
        tier=tier,
        topic_category=topic_category,
    )
    
    results = []
    for paper in papers:
        # Get full scoring data
        paper_data = db.get_paper_with_scores(paper.arxiv_id)
        if paper_data:
            results.append(RankedPaperResponse(
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                abstract=paper.abstract[:500] + "..." if len(paper.abstract) > 500 else paper.abstract,
                authors_str=paper.authors_str,
                published=paper.published.isoformat(),
                pdf_url=paper.pdf_url,
                arxiv_url=paper.arxiv_url,
                composite_score=paper_data.get("composite_score", 0),
                rank_tier=paper_data.get("rank_tier", ""),
                topic_category=paper_data.get("topic_category", ""),
                topic_score=paper_data.get("topic_score", 0),
                production_score=paper_data.get("production_score", 0),
                credibility_score=paper_data.get("credibility_score", 0),
                has_code=paper.has_code,
                benchmark_flags=paper_data.get("benchmark_flags", []),
            ))
    
    return results


@app.get("/api/paper/{arxiv_id}/score")
async def get_paper_score(arxiv_id: str):
    """Get detailed scoring breakdown for a paper."""
    paper_data = db.get_paper_with_scores(arxiv_id)
    if not paper_data:
        raise HTTPException(status_code=404, detail=f"Paper not found: {arxiv_id}")
    
    if not paper_data.get("scored_at"):
        # Paper hasn't been scored yet, score it now
        paper = db.get_paper(arxiv_id)
        result = score_paper(paper)
        db.save_paper_score(
            arxiv_id=arxiv_id,
            topic_score=result.topic_relevance.score,
            topic_category=result.topic_relevance.topic_category,
            production_score=result.production_readiness.score,
            credibility_score=result.credibility.score,
            composite_score=result.composite_score,
            rank_tier=result.rank_tier,
            benchmark_flags=json.dumps(result.benchmark_flags.flags),
        )
        paper_data = db.get_paper_with_scores(arxiv_id)
    
    return {
        "arxiv_id": arxiv_id,
        "title": paper_data.get("title"),
        "composite_score": paper_data.get("composite_score", 0),
        "rank_tier": paper_data.get("rank_tier", ""),
        "breakdown": {
            "topic": {
                "score": paper_data.get("topic_score", 0),
                "category": paper_data.get("topic_category", ""),
                "weight": "25%",
            },
            "production_readiness": {
                "score": paper_data.get("production_score", 0),
                "weight": "35%",
            },
            "credibility": {
                "score": paper_data.get("credibility_score", 0),
                "weight": "25%",
            },
            "citation_bonus": {
                "score": paper_data.get("citation_count", 0),
                "weight": "15%",
                "note": "Only applies to papers >30 days old",
            },
        },
        "benchmark_flags": paper_data.get("benchmark_flags", []),
        "scored_at": paper_data.get("scored_at"),
    }


@app.get("/api/topic-categories")
async def get_topic_categories():
    """Get list of topic categories for filtering."""
    from .topic_relevance import get_topic_categories
    return {"categories": get_topic_categories()}

