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
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
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
    papers_last_7_days: int
    top_categories: list[tuple[str, int]]
    embeddings_count: Optional[int]
    semantic_search_available: bool


class FetchRequest(BaseModel):
    days: int = 7
    max_results: int = 100
    enrich: bool = False


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
        papers_last_7_days=stats["papers_last_7_days"],
        top_categories=stats["top_categories"],
        embeddings_count=embeddings_store.get_count() if embeddings_store else None,
        semantic_search_available=embeddings_store is not None,
    )


def _fetch_papers_task(days: int, max_results: int, enrich: bool):
    """Background task to fetch papers from arXiv."""
    global db, embeddings_store
    
    client = ArxivClient()
    papers = client.fetch_llm_inference_papers(days_back=days, max_results=max_results)
    
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
    """
    background_tasks.add_task(_fetch_papers_task, request.days, request.max_results, request.enrich)
    
    return FetchResponse(
        fetched=0,
        new_papers=0,
        duplicates=0,
        message=f"Fetching papers from the last {request.days} days in background...",
    )


@app.post("/api/sync-embeddings")
async def sync_embeddings():
    """Sync all papers from database to embeddings store."""
    if not embeddings_store:
        raise HTTPException(status_code=503, detail="Embeddings store not available")
    
    count = embeddings_store.sync_from_database(db, limit=5000)
    return {"synced": count, "total": embeddings_store.get_count()}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": db is not None,
        "embeddings": embeddings_store is not None,
    }
