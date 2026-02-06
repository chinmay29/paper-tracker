"""
PDF text extraction module for analyzing full paper content.

Downloads PDFs from arXiv and extracts text for improved scoring accuracy.
"""

import io
import logging
import os
import hashlib
import time
from pathlib import Path
from typing import Optional
import requests
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# Cache directory for downloaded PDFs
DEFAULT_CACHE_DIR = Path.home() / ".paper_tracker" / "pdf_cache"


class PDFExtractor:
    """
    Downloads and extracts text from arXiv PDFs.
    
    Features:
    - Caches downloaded PDFs to avoid re-downloading
    - Rate limiting to respect arXiv's terms of service
    - Extracts text from all pages
    - Handles extraction errors gracefully
    """
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        rate_limit_seconds: float = 3.0,  # arXiv recommends 3s between requests
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request_time = 0.0
        
        # Text cache (in memory) - arxiv_id -> extracted text
        self._text_cache: dict[str, str] = {}
    
    def _get_cache_path(self, arxiv_id: str) -> Path:
        """Get the cache file path for an arXiv ID."""
        # Sanitize arxiv_id for filesystem
        safe_id = arxiv_id.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_id}.pdf"
    
    def _get_text_cache_path(self, arxiv_id: str) -> Path:
        """Get the text cache file path for an arXiv ID."""
        safe_id = arxiv_id.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_id}.txt"
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_time = time.time()
    
    def download_pdf(self, arxiv_id: str, pdf_url: str) -> Optional[Path]:
        """
        Download a PDF from arXiv, caching it locally.
        
        Args:
            arxiv_id: The arXiv paper ID
            pdf_url: URL to the PDF
            
        Returns:
            Path to the cached PDF file, or None on failure
        """
        cache_path = self._get_cache_path(arxiv_id)
        
        # Return cached file if exists
        if cache_path.exists():
            logger.debug(f"Using cached PDF for {arxiv_id}")
            return cache_path
        
        try:
            self._rate_limit()
            logger.info(f"Downloading PDF for {arxiv_id} from {pdf_url}")
            
            response = requests.get(
                pdf_url,
                timeout=60,
                headers={
                    "User-Agent": "PaperTracker/1.0 (Research paper scoring tool)"
                }
            )
            response.raise_for_status()
            
            # Write to cache
            with open(cache_path, "wb") as f:
                f.write(response.content)
            
            logger.info(f"Cached PDF for {arxiv_id} ({len(response.content)} bytes)")
            return cache_path
            
        except requests.RequestException as e:
            logger.error(f"Failed to download PDF for {arxiv_id}: {e}")
            return None
        except IOError as e:
            logger.error(f"Failed to cache PDF for {arxiv_id}: {e}")
            return None
    
    def extract_text(self, arxiv_id: str, pdf_url: str) -> Optional[str]:
        """
        Extract text from a paper's PDF.
        
        Args:
            arxiv_id: The arXiv paper ID
            pdf_url: URL to the PDF
            
        Returns:
            Extracted text, or None on failure
        """
        # Check in-memory cache first
        if arxiv_id in self._text_cache:
            return self._text_cache[arxiv_id]
        
        # Check text file cache
        text_cache_path = self._get_text_cache_path(arxiv_id)
        if text_cache_path.exists():
            try:
                text = text_cache_path.read_text(encoding="utf-8")
                self._text_cache[arxiv_id] = text
                return text
            except IOError:
                pass
        
        # Download and extract
        pdf_path = self.download_pdf(arxiv_id, pdf_url)
        if not pdf_path:
            return None
        
        try:
            text = self._extract_from_file(pdf_path)
            if text:
                # Cache the extracted text
                self._text_cache[arxiv_id] = text
                try:
                    text_cache_path.write_text(text, encoding="utf-8")
                except IOError as e:
                    logger.warning(f"Could not cache text for {arxiv_id}: {e}")
                return text
        except Exception as e:
            logger.error(f"Failed to extract text from {arxiv_id}: {e}")
        
        return None
    
    def _extract_from_file(self, pdf_path: Path) -> Optional[str]:
        """Extract text from a PDF file."""
        try:
            reader = PdfReader(str(pdf_path))
            
            text_parts = []
            for page_num, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num}: {e}")
                    continue
            
            if not text_parts:
                logger.warning(f"No text extracted from {pdf_path}")
                return None
            
            full_text = "\n\n".join(text_parts)
            logger.debug(f"Extracted {len(full_text)} characters from {pdf_path}")
            return full_text
            
        except Exception as e:
            logger.error(f"Failed to read PDF {pdf_path}: {e}")
            return None
    
    def get_combined_text(
        self,
        arxiv_id: str,
        pdf_url: str,
        title: str,
        abstract: str,
    ) -> str:
        """
        Get combined text for scoring: abstract + full paper text.
        
        If PDF extraction fails, returns just title + abstract.
        Full text is truncated to avoid performance issues.
        
        Args:
            arxiv_id: The arXiv paper ID
            pdf_url: URL to the PDF
            title: Paper title
            abstract: Paper abstract
            
        Returns:
            Combined text for scoring
        """
        base_text = f"{title}\n\n{abstract}"
        
        pdf_text = self.extract_text(arxiv_id, pdf_url)
        if pdf_text:
            # Truncate to reasonable size (first 50K chars covers most content)
            # This typically includes abstract, intro, methods, experiments
            max_chars = 50000
            if len(pdf_text) > max_chars:
                pdf_text = pdf_text[:max_chars] + "..."
            
            return f"{base_text}\n\n--- FULL PAPER TEXT ---\n\n{pdf_text}"
        
        return base_text
    
    def clear_cache(self):
        """Clear all cached PDFs and text files."""
        if self.cache_dir.exists():
            import shutil
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._text_cache.clear()
        logger.info("Cleared PDF cache")
    
    def get_cache_stats(self) -> dict:
        """Get statistics about the cache."""
        if not self.cache_dir.exists():
            return {"pdf_count": 0, "text_count": 0, "total_size_mb": 0}
        
        pdf_files = list(self.cache_dir.glob("*.pdf"))
        txt_files = list(self.cache_dir.glob("*.txt"))
        
        total_size = sum(f.stat().st_size for f in pdf_files + txt_files)
        
        return {
            "pdf_count": len(pdf_files),
            "text_count": len(txt_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dir": str(self.cache_dir),
        }


# Global instance for convenience
_extractor: Optional[PDFExtractor] = None


def get_extractor() -> PDFExtractor:
    """Get the global PDF extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = PDFExtractor()
    return _extractor


def extract_paper_text(
    arxiv_id: str,
    pdf_url: str,
    title: str = "",
    abstract: str = "",
) -> str:
    """
    Convenience function to extract text for a paper.
    
    Returns combined title + abstract + full text (if available).
    """
    extractor = get_extractor()
    return extractor.get_combined_text(arxiv_id, pdf_url, title, abstract)
