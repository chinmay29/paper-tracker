"""SQLite database for storing paper metadata."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Paper


DEFAULT_DB_PATH = Path.home() / ".paper_tracker" / "papers.db"


class Database:
    """SQLite database for paper storage."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        # Use check_same_thread=False for multi-threaded async access
        # timeout=30 to handle briefly locked database
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0
        )
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    arxiv_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    abstract TEXT,
                    authors TEXT,
                    categories TEXT,
                    published TEXT,
                    updated TEXT,
                    pdf_url TEXT,
                    arxiv_url TEXT,
                    has_code INTEGER DEFAULT 0,
                    github_url TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    relevance_score REAL DEFAULT 0,
                    is_read INTEGER DEFAULT 0,
                    citation_count INTEGER DEFAULT 0,
                    reference_count INTEGER DEFAULT 0,
                    influential_citation_count INTEGER DEFAULT 0,
                    venue TEXT DEFAULT '',
                    has_open_pdf INTEGER DEFAULT 0,
                    -- Scoring columns (Phase 2)
                    topic_score REAL DEFAULT 0,
                    topic_category TEXT DEFAULT '',
                    production_score REAL DEFAULT 0,
                    credibility_score REAL DEFAULT 0,
                    composite_score REAL DEFAULT 0,
                    rank_tier TEXT DEFAULT '',
                    benchmark_flags TEXT DEFAULT '[]',
                    scored_at TEXT
                )
            """)
            
            # Add new columns if they don't exist (migration)
            migrations = [
                "ALTER TABLE papers ADD COLUMN citation_count INTEGER DEFAULT 0",
                "ALTER TABLE papers ADD COLUMN reference_count INTEGER DEFAULT 0",
                "ALTER TABLE papers ADD COLUMN influential_citation_count INTEGER DEFAULT 0",
                "ALTER TABLE papers ADD COLUMN venue TEXT DEFAULT ''",
                "ALTER TABLE papers ADD COLUMN has_open_pdf INTEGER DEFAULT 0",
                # Phase 2 scoring columns
                "ALTER TABLE papers ADD COLUMN topic_score REAL DEFAULT 0",
                "ALTER TABLE papers ADD COLUMN topic_category TEXT DEFAULT ''",
                "ALTER TABLE papers ADD COLUMN production_score REAL DEFAULT 0",
                "ALTER TABLE papers ADD COLUMN credibility_score REAL DEFAULT 0",
                "ALTER TABLE papers ADD COLUMN composite_score REAL DEFAULT 0",
                "ALTER TABLE papers ADD COLUMN rank_tier TEXT DEFAULT ''",
                "ALTER TABLE papers ADD COLUMN benchmark_flags TEXT DEFAULT '[]'",
                "ALTER TABLE papers ADD COLUMN scored_at TEXT",
            ]
            
            for migration in migrations:
                try:
                    conn.execute(migration)
                except sqlite3.OperationalError:
                    pass
            
            # Create indices for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_published ON papers(published)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_categories ON papers(categories)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_citations ON papers(citation_count)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_composite_score ON papers(composite_score)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rank_tier ON papers(rank_tier)
            """)
            conn.commit()
    
    def insert_paper(self, paper: Paper) -> bool:
        """Insert a paper, returning True if new, False if duplicate."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO papers (
                        arxiv_id, title, abstract, authors, categories,
                        published, updated, pdf_url, arxiv_url, has_code, github_url,
                        citation_count, reference_count, influential_citation_count, venue, has_open_pdf
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    paper.arxiv_id,
                    paper.title,
                    paper.abstract,
                    ",".join(paper.authors),
                    ",".join(paper.categories),
                    paper.published.isoformat(),
                    paper.updated.isoformat(),
                    paper.pdf_url,
                    paper.arxiv_url,
                    int(paper.has_code),
                    paper.github_url,
                    paper.citation_count,
                    paper.reference_count,
                    paper.influential_citation_count,
                    paper.venue,
                    int(paper.has_open_pdf),
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # Duplicate
    
    def update_paper(self, paper: Paper) -> bool:
        """Update an existing paper with new data."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE papers SET
                    citation_count = ?,
                    reference_count = ?,
                    influential_citation_count = ?,
                    venue = ?,
                    has_open_pdf = ?,
                    has_code = ?,
                    github_url = ?
                WHERE arxiv_id = ?
            """, (
                paper.citation_count,
                paper.reference_count,
                paper.influential_citation_count,
                paper.venue,
                int(paper.has_open_pdf),
                int(paper.has_code),
                paper.github_url or "",
                paper.arxiv_id,
            ))
            conn.commit()
            return cursor.rowcount > 0
    
    def insert_papers(self, papers: list[Paper]) -> tuple[int, int]:
        """Insert multiple papers. Returns (new_count, duplicate_count)."""
        new_count = 0
        dup_count = 0
        for paper in papers:
            if self.insert_paper(paper):
                new_count += 1
            else:
                dup_count += 1
        return new_count, dup_count
    
    def get_paper(self, arxiv_id: str) -> Optional[Paper]:
        """Get a paper by arXiv ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)
            ).fetchone()
            if row:
                return Paper.from_dict(dict(row))
        return None
    
    def list_papers(
        self,
        limit: int = 20,
        offset: int = 0,
        since_days: Optional[int] = None,
        category: Optional[str] = None,
    ) -> list[Paper]:
        """List papers with optional filters."""
        query = "SELECT * FROM papers WHERE 1=1"
        params = []
        
        if since_days:
            cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            from datetime import timedelta
            cutoff = cutoff - timedelta(days=since_days)
            query += " AND published >= ?"
            params.append(cutoff.isoformat())
        
        if category:
            query += " AND categories LIKE ?"
            params.append(f"%{category}%")
        
        query += " ORDER BY published DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [Paper.from_dict(dict(row)) for row in rows]
    
    def search_papers(self, keyword: str, limit: int = 20) -> list[Paper]:
        """Search papers by keyword in title or abstract."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM papers 
                WHERE title LIKE ? OR abstract LIKE ?
                ORDER BY published DESC
                LIMIT ?
            """, (f"%{keyword}%", f"%{keyword}%", limit)).fetchall()
            return [Paper.from_dict(dict(row)) for row in rows]
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            recent = conn.execute("""
                SELECT COUNT(*) FROM papers 
                WHERE published >= date('now', '-7 days')
            """).fetchone()[0]
            scored = conn.execute("""
                SELECT COUNT(*) FROM papers 
                WHERE scored_at IS NOT NULL
            """).fetchone()[0]
            categories = conn.execute("""
                SELECT categories, COUNT(*) as cnt FROM papers 
                GROUP BY categories ORDER BY cnt DESC LIMIT 10
            """).fetchall()
            
            # Tier distribution
            tiers = conn.execute("""
                SELECT rank_tier, COUNT(*) as cnt FROM papers 
                WHERE rank_tier != ''
                GROUP BY rank_tier ORDER BY rank_tier
            """).fetchall()
            
            return {
                "total_papers": total,
                "papers_last_7_days": recent,
                "scored_papers": scored,
                "top_categories": [(row[0], row[1]) for row in categories],
                "tier_distribution": {row[0]: row[1] for row in tiers},
            }
    
    def save_paper_score(
        self,
        arxiv_id: str,
        topic_score: float,
        topic_category: str,
        production_score: float,
        credibility_score: float,
        composite_score: float,
        rank_tier: str,
        benchmark_flags: str,  # JSON string
    ) -> bool:
        """Save scoring results for a paper."""
        from datetime import datetime
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE papers SET
                    topic_score = ?,
                    topic_category = ?,
                    production_score = ?,
                    credibility_score = ?,
                    composite_score = ?,
                    rank_tier = ?,
                    benchmark_flags = ?,
                    scored_at = ?
                WHERE arxiv_id = ?
            """, (
                topic_score,
                topic_category,
                production_score,
                credibility_score,
                composite_score,
                rank_tier,
                benchmark_flags,
                datetime.now().isoformat(),
                arxiv_id,
            ))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_unscored_papers(self, limit: int = 100) -> list[Paper]:
        """Get papers that haven't been scored yet."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM papers 
                WHERE scored_at IS NULL
                ORDER BY published DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [Paper.from_dict(dict(row)) for row in rows]
    
    def list_papers_ranked(
        self,
        limit: int = 20,
        offset: int = 0,
        min_score: float = 0,
        tier: Optional[str] = None,
        topic_category: Optional[str] = None,
    ) -> list[Paper]:
        """List papers ranked by composite score."""
        query = "SELECT * FROM papers WHERE scored_at IS NOT NULL"
        params = []
        
        if min_score > 0:
            query += " AND composite_score >= ?"
            params.append(min_score)
        
        if tier:
            query += " AND rank_tier = ?"
            params.append(tier.upper())
        
        if topic_category:
            query += " AND topic_category = ?"
            params.append(topic_category)
        
        query += " ORDER BY composite_score DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [Paper.from_dict(dict(row)) for row in rows]
    
    def get_paper_with_scores(self, arxiv_id: str) -> Optional[dict]:
        """Get paper with all scoring data."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)
            ).fetchone()
            if row:
                data = dict(row)
                # Parse benchmark_flags from JSON
                import json
                try:
                    data["benchmark_flags"] = json.loads(data.get("benchmark_flags", "[]"))
                except (json.JSONDecodeError, TypeError):
                    data["benchmark_flags"] = []
                return data
        return None

