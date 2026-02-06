"""Credibility scoring based on author affiliations and venues."""

import re
from typing import Optional

from .models import Paper
from .scoring import Credibility


# Top-tier industry affiliations
TIER_1_INDUSTRY = [
    "nvidia", "meta", "google", "deepmind", "openai", "anthropic",
    "microsoft", "amazon", "aws", "apple", "alibaba", "bytedance",
    "tencent", "baidu", "huggingface", "cohere", "together ai",
    "together.ai", "databricks", "mosaic", "anyscale",
]

# Top-tier academic institutions
TIER_1_ACADEMIC = [
    "stanford", "berkeley", "mit", "cmu", "carnegie mellon",
    "princeton", "harvard", "yale", "cornell", "caltech",
    "toronto", "mila", "eth zurich", "oxford", "cambridge",
    "tsinghua", "peking", "ucl", "epfl", "inria",
    "washington", "georgia tech", "michigan", "illinois",
]

# Mid-tier affiliations
TIER_2_AFFILIATIONS = [
    "intel", "amd", "qualcomm", "ibm", "samsung", "huawei",
    "salesforce", "adobe", "uber", "linkedin", "twitter",
]

# Top-tier venues for ML systems papers
TOP_VENUES = {
    # Systems conferences
    "osdi": 3, "sosp": 3, "nsdi": 3, "atc": 2, "eurosys": 2,
    "mlsys": 3, "asplos": 3, "isca": 2, "micro": 2,
    # ML conferences
    "neurips": 3, "nips": 3, "icml": 3, "iclr": 3,
    "aaai": 2, "ijcai": 2, "acl": 2, "emnlp": 2, "naacl": 2,
    # Workshops at top venues
    "neurips workshop": 1, "icml workshop": 1, "iclr workshop": 1,
}

# Patterns to extract affiliations from author names
AFFILIATION_PATTERNS = [
    r"\(([^)]+)\)",  # (Affiliation)
    r"@(\w+)",       # @company
    r",\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*$",  # Name, University
]


def compute_credibility(
    paper: Paper,
    author_h_indices: Optional[dict[str, int]] = None,
) -> Credibility:
    """
    Compute credibility score for a paper.
    
    Args:
        paper: Paper object to score
        author_h_indices: Optional dict mapping author names to h-indices
        
    Returns:
        Credibility object with scores and details
    """
    # Combine all text for affiliation detection
    text = f"{' '.join(paper.authors)} {paper.abstract}".lower()
    
    # 1. Detect affiliations (35 points max)
    affiliation_score = 0
    detected_affiliations = []
    top_tier_affiliations = []
    
    # Check for tier 1 industry
    for affil in TIER_1_INDUSTRY:
        if affil in text:
            if affil not in detected_affiliations:
                detected_affiliations.append(affil)
                if affil not in top_tier_affiliations:
                    top_tier_affiliations.append(affil)
                affiliation_score += 15
    
    # Check for tier 1 academic
    for affil in TIER_1_ACADEMIC:
        if affil in text:
            if affil not in detected_affiliations:
                detected_affiliations.append(affil)
                if affil not in top_tier_affiliations:
                    top_tier_affiliations.append(affil)
                affiliation_score += 10
    
    # Check for tier 2
    for affil in TIER_2_AFFILIATIONS:
        if affil in text:
            if affil not in detected_affiliations:
                detected_affiliations.append(affil)
                affiliation_score += 5
    
    affiliation_score = min(35, affiliation_score)
    
    # 2. Author h-index (25 points max)
    h_index_score = 0
    max_h_index = 0
    
    if author_h_indices:
        for author, h_index in author_h_indices.items():
            if h_index > max_h_index:
                max_h_index = h_index
        
        # Scoring based on h-index
        # h >= 50: 25 points (senior researcher)
        # h >= 30: 20 points (established researcher)
        # h >= 15: 15 points (active researcher)
        # h >= 5: 10 points (early career)
        if max_h_index >= 50:
            h_index_score = 25
        elif max_h_index >= 30:
            h_index_score = 20
        elif max_h_index >= 15:
            h_index_score = 15
        elif max_h_index >= 5:
            h_index_score = 10
    
    # 3. Venue scoring (30 points max)
    venue_score = 0
    venue = paper.venue.lower() if paper.venue else ""
    venue_tier = "preprint"
    is_peer_reviewed = False
    
    # Check venue against known conferences
    for venue_name, points in TOP_VENUES.items():
        if venue_name in venue:
            venue_score = points * 10  # Scale to max 30
            venue_tier = "top" if points >= 3 else "mid"
            is_peer_reviewed = True
            break
    
    venue_score = min(30, venue_score)
    
    # If no venue but has citations, likely peer-reviewed
    if not is_peer_reviewed and paper.citation_count > 10:
        venue_tier = "mid"
        venue_score = 10
    
    # 4. Paper recency boost (10 points max)
    # Newer papers from good authors get a small boost
    recency_score = 0
    if paper.is_recent and affiliation_score > 0:
        recency_score = 10
    
    # Total score
    total_score = affiliation_score + h_index_score + venue_score + recency_score
    
    return Credibility(
        score=round(total_score, 2),
        author_affiliations=detected_affiliations[:10],  # Limit to 10
        top_tier_affiliations=top_tier_affiliations[:5],  # Limit to 5
        max_h_index=max_h_index,
        venue=paper.venue or "",
        venue_tier=venue_tier,
        is_peer_reviewed=is_peer_reviewed,
    )
