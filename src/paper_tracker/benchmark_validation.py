"""Benchmark validation and suspicious claim detection."""

import re
from typing import Optional

from .models import Paper
from .scoring import BenchmarkFlags


# Known baseline systems with version patterns
BASELINE_VERSIONS = {
    "vllm": {
        "current": ["0.6", "0.5", "0.4.3"],
        "outdated": ["0.1", "0.2", "0.3", "0.4.0", "0.4.1", "0.4.2"],
        "pattern": r"vllm\s*(?:v|version)?\s*([0-9.]+)",
    },
    "tensorrt-llm": {
        "current": ["0.9", "0.10", "0.11", "0.12"],
        "outdated": ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7"],
        "pattern": r"tensorrt[- ]?llm\s*(?:v|version)?\s*([0-9.]+)",
    },
    "transformers": {
        "current": ["4.4", "4.3", "4.2"],
        "outdated": ["4.0", "3."],
        "pattern": r"transformers\s*(?:v|version)?\s*([0-9.]+)",
    },
}

# Speedup thresholds
REASONABLE_SPEEDUP_MAX = 10.0
SUSPICIOUS_SPEEDUP_THRESHOLD = 5.0


def detect_speedup_claims(text: str) -> list[tuple[float, str]]:
    """
    Detect speedup claims in text.
    
    Returns list of (speedup_value, context) tuples.
    """
    speedups = []
    
    patterns = [
        r"(\d+(?:\.\d+)?)[xX]\s*(?:faster|speedup|improvement|gain)",
        r"(\d+(?:\.\d+)?)\s*times?\s*(?:faster|speedup|improvement)",
        r"speedup\s*(?:of|:)?\s*(\d+(?:\.\d+)?)[xX]?",
        r"(\d+(?:\.\d+)?)[xX]\s*(?:latency\s+)?reduction",
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                speedup = float(match.group(1))
                context = text[max(0, match.start()-30):match.end()+30]
                speedups.append((speedup, context.strip()))
            except (ValueError, IndexError):
                continue
    
    return speedups


def detect_outdated_baselines(text: str) -> list[str]:
    """
    Detect if paper compares against outdated baseline versions.
    
    Returns list of warning messages.
    """
    warnings = []
    
    for system, info in BASELINE_VERSIONS.items():
        pattern = info["pattern"]
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            version = match.group(1)
            
            # Check if version is outdated
            for outdated in info["outdated"]:
                if version.startswith(outdated):
                    warnings.append(
                        f"Compares to outdated {system} v{version}"
                    )
                    break
    
    return warnings


def detect_missing_ablations(paper: Paper) -> bool:
    """
    Check if paper appears to be missing ablation studies.
    
    Only flags for papers that make specific claims but don't mention ablation.
    """
    text = paper.abstract.lower()
    
    # Papers making strong claims should have ablations
    claim_patterns = [
        r"state.?of.?the.?art",
        r"outperform",
        r"sota",
        r"best.?performing",
        r"significant.?improvement",
    ]
    
    makes_strong_claims = any(
        re.search(p, text) for p in claim_patterns
    )
    
    mentions_ablation = any(
        term in text for term in ["ablation", "ablate", "component analysis"]
    )
    
    # Only flag if making claims but no ablation mentioned
    return makes_strong_claims and not mentions_ablation


def compute_benchmark_flags(
    paper: Paper,
    full_text: Optional[str] = None,
) -> BenchmarkFlags:
    """
    Compute benchmark validation flags for a paper.
    
    Args:
        paper: Paper object to analyze
        full_text: Optional full paper text (extracted from PDF)
        
    Returns:
        BenchmarkFlags object with warnings
    """
    # Use full text if provided, otherwise just title + abstract
    if full_text:
        text = full_text.lower()
    else:
        text = f"{paper.title} {paper.abstract}".lower()
    flags = []
    
    # 1. Check for unrealistic speedup claims
    unrealistic_speedup = False
    speedup_claimed = None
    speedups = detect_speedup_claims(text)
    
    if speedups:
        max_speedup = max(s[0] for s in speedups)
        speedup_claimed = max_speedup
        
        if max_speedup > REASONABLE_SPEEDUP_MAX:
            flags.append(
                f"Claims {max_speedup}x speedup - verify methodology carefully"
            )
            unrealistic_speedup = True
        elif max_speedup > SUSPICIOUS_SPEEDUP_THRESHOLD:
            flags.append(
                f"Claims {max_speedup}x speedup - worth verifying"
            )
    
    # 2. Check for outdated baselines
    outdated_baselines = False
    outdated_details = detect_outdated_baselines(text)
    
    if outdated_details:
        outdated_baselines = True
        for detail in outdated_details:
            flags.append(detail)
    
    # 3. Check for missing ablations
    missing_ablations = detect_missing_ablations(paper)
    
    if missing_ablations and paper.citation_count == 0:
        # Only flag for new/uncited papers
        flags.append("Makes strong claims but no ablation study mentioned")
    
    # 4. Additional quality checks
    
    # Check for vague hardware mentions
    if "gpu" in text and not re.search(r"[AHVT]\d{3,4}", paper.abstract, re.IGNORECASE):
        # Mentions GPU but doesn't specify model
        if "speedup" in text or "faster" in text:
            flags.append("Performance claims without specific GPU model")
    
    # Check for missing experimental details
    if "outperform" in text and "table" not in text and "figure" not in text:
        # Claims improvements but may not show data
        pass  # Too noisy, skip for now
    
    return BenchmarkFlags(
        flags=flags,
        unrealistic_speedup=unrealistic_speedup,
        speedup_claimed=speedup_claimed,
        outdated_baselines=outdated_baselines,
        outdated_baseline_details=outdated_details,
        missing_ablations=missing_ablations,
    )
