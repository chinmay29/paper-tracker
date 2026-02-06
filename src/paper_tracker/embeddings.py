"""ChromaDB embeddings for semantic search of papers."""

import logging
from pathlib import Path
from typing import Optional

try:
    import chromadb
    CHROMADB_AVAILABLE = True
    # Check which API version we have
    try:
        from chromadb.config import Settings
        HAS_SETTINGS = True
    except ImportError:
        HAS_SETTINGS = False
except ImportError:
    CHROMADB_AVAILABLE = False
    HAS_SETTINGS = False

from .models import Paper
from .database import Database

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "paper_abstracts"
DEFAULT_PERSIST_DIR = Path.home() / ".paper_tracker" / "chroma_db"


class EmbeddingsStore:
    """ChromaDB-based embeddings store for semantic paper search."""
    
    def __init__(self, persist_dir: Optional[Path] = None, collection_name: str = DEFAULT_COLLECTION):
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb is required for semantic search. Install with: pip install chromadb")
        
        self.persist_dir = persist_dir or DEFAULT_PERSIST_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Handle different ChromaDB versions
        try:
            if HAS_SETTINGS:
                self.client = chromadb.PersistentClient(
                    path=str(self.persist_dir),
                    settings=Settings(anonymized_telemetry=False)
                )
            else:
                # Older API or different version
                self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        except (TypeError, AttributeError):
            # Fallback for very old versions
            self.client = chromadb.Client(chromadb.config.Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.persist_dir),
                anonymized_telemetry=False
            ))
        
        # Use default embedding function (all-MiniLM-L6-v2)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info(f"Initialized embeddings store at {self.persist_dir}")
    
    def add_paper(self, paper: Paper) -> bool:
        """Add a paper to the embeddings store."""
        try:
            # Combine title and abstract for better semantic representation
            text = f"{paper.title}\n\n{paper.abstract}"
            
            self.collection.upsert(
                ids=[paper.arxiv_id],
                documents=[text],
                metadatas=[{
                    "title": paper.title,
                    "authors": paper.authors_str,
                    "published": paper.published.isoformat(),
                    "category": paper.primary_category,
                }]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add paper {paper.arxiv_id}: {e}")
            return False
    
    def add_papers(self, papers: list[Paper]) -> int:
        """Add multiple papers. Returns count of successfully added."""
        count = 0
        for paper in papers:
            if self.add_paper(paper):
                count += 1
        return count
    
    def search(self, query: str, limit: int = 20) -> list[tuple[str, float]]:
        """
        Search for papers semantically similar to the query.
        
        Returns list of (arxiv_id, similarity_score) tuples.
        """
        if self.collection.count() == 0:
            return []
        
        results = self.collection.query(
            query_texts=[query],
            n_results=min(limit, self.collection.count()),
            include=["distances"]
        )
        
        if not results["ids"] or not results["ids"][0]:
            return []
        
        # Convert distances to similarity scores (1 - distance for cosine)
        ids = results["ids"][0]
        distances = results["distances"][0] if results["distances"] else [0] * len(ids)
        
        return [(id_, 1 - dist) for id_, dist in zip(ids, distances)]
    
    def sync_from_database(self, db: Database, limit: int = 1000) -> int:
        """Sync papers from SQLite database to embeddings store."""
        papers = db.list_papers(limit=limit)
        
        # Check which papers are already in the collection
        existing_ids = set(self.collection.get()["ids"])
        new_papers = [p for p in papers if p.arxiv_id not in existing_ids]
        
        if new_papers:
            count = self.add_papers(new_papers)
            logger.info(f"Synced {count} new papers to embeddings store")
            return count
        return 0
    
    def get_count(self) -> int:
        """Get the number of papers in the embeddings store."""
        return self.collection.count()
    
    def delete_paper(self, arxiv_id: str) -> bool:
        """Delete a paper from the embeddings store."""
        try:
            self.collection.delete(ids=[arxiv_id])
            return True
        except Exception as e:
            logger.error(f"Failed to delete paper {arxiv_id}: {e}")
            return False
