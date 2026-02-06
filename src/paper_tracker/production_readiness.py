"""Production-readiness scoring for papers."""

import re
from typing import Optional

from .models import Paper
from .scoring import ProductionReadiness


# Standard benchmarks to look for
BENCHMARKS = {
    # LLM benchmarks
    "mmlu": 3, "hellaswag": 2, "winogrande": 2, "arc": 2,
    "gsm8k": 2, "humaneval": 3, "mbpp": 2, "mt-bench": 3,
    "alpaca eval": 2, "alpacaeval": 2,
    # Inference benchmarks
    "sharegpt": 3, "lmsys": 2, "chatbot arena": 2,
    "longbench": 2, "needle in a haystack": 2,
    # Performance metrics keywords
    "latency": 2, "throughput": 3, "tokens per second": 3,
    "time to first token": 3, "ttft": 3, "tps": 2,
    "requests per second": 2, "qps": 2,
}

# Hardware identifiers  
HARDWARE_PATTERNS = {
    # NVIDIA GPUs
    r"\bA100\b": "A100",
    r"\bH100\b": "H100", 
    r"\bH200\b": "H200",
    r"\bA6000\b": "A6000",
    r"\bL40S?\b": "L40",
    r"\bV100\b": "V100",
    r"\bT4\b": "T4",
    r"\b40[89]0\b": "RTX 4000",
    r"\b30[789]0\b": "RTX 3000",
    r"\bGH200\b": "GH200",
    r"\bB100\b": "B100",
    r"\bB200\b": "B200",
    # AMD GPUs
    r"\bMI300[AX]?\b": "MI300",
    r"\bMI250\b": "MI250",
    # TPUs
    r"\bTPU v[345]\b": "TPU",
    r"\bTPU-v[345]\b": "TPU",
    # AWS/Cloud
    r"\bp4d\b": "AWS P4d",
    r"\bp5\b": "AWS P5",
}

# Scale indicators
SCALE_PATTERNS = [
    (r"batch size[:\s]+(\d+)", lambda m: int(m.group(1)) >= 32),
    (r"batch[:\s]+(\d+)", lambda m: int(m.group(1)) >= 32),
    (r"(\d+)\s*(?:gpus?|devices?|nodes?)", lambda m: int(m.group(1)) >= 2),
    (r"multi.?gpu", lambda m: True),
    (r"multi.?node", lambda m: True),
    (r"distributed", lambda m: True),
    (r"8.?way", lambda m: True),
    (r"tensor.?parallel", lambda m: True),
    (r"pipeline.?parallel", lambda m: True),
]

# Baseline systems to compare against
BASELINE_SYSTEMS = [
    "vllm", "tensorrt-llm", "tensorrt llm", "trt-llm",
    "fastertransformer", "faster transformer",
    "huggingface", "transformers",
    "deepspeed", "megatron",
    "text generation inference", "tgi",
    "orca", "sglang", "lmdeploy",
    "llama.cpp", "ollama",
]

# Real workload indicators
REAL_WORKLOAD_PATTERNS = [
    "sharegpt", "lmsys", "chatbot arena",
    "production workload", "production traffic",
    "real-world", "real world", "real requests",
    "user requests", "user queries",
    "deployment", "in production",
]

# GitHub patterns
GITHUB_PATTERNS = [
    r"github\.com/[\w\-]+/[\w\-]+",
    r"github:\s*[\w\-]+/[\w\-]+",
    r"code:?\s*[\w\-]+/[\w\-]+",
    r"available at github",
    r"code is available",
    r"open.?source",
]


def compute_production_readiness(
    paper: Paper,
    papers_with_code_result: Optional[dict] = None,
) -> ProductionReadiness:
    """
    Compute production-readiness score for a paper.
    
    Args:
        paper: Paper object to score
        papers_with_code_result: Optional result from Papers with Code API
        
    Returns:
        ProductionReadiness object with scores and signals
    """
    text = f"{paper.title} {paper.abstract}".lower()
    
    # 1. Code availability (25 points max)
    code_score = 0
    has_code = paper.has_code
    github_url = paper.github_url
    
    # Check abstract for GitHub links
    for pattern in GITHUB_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            has_code = True
            if "github.com" in match.group(0):
                github_url = f"https://{match.group(0)}"
            break
    
    # Use Papers with Code data if available
    if papers_with_code_result:
        if papers_with_code_result.get("has_code"):
            has_code = True
        if papers_with_code_result.get("github_url"):
            github_url = papers_with_code_result["github_url"]
    
    if has_code:
        code_score = 25
    
    # 2. Reproducible benchmarks (20 points max)
    benchmark_score = 0
    benchmarks_mentioned = []
    
    for benchmark, weight in BENCHMARKS.items():
        if benchmark in text:
            benchmarks_mentioned.append(benchmark)
            benchmark_score += weight
    
    benchmark_score = min(20, benchmark_score)
    has_reproducible_benchmarks = len(benchmarks_mentioned) >= 2
    
    # 3. Hardware specified (15 points max)
    hardware_score = 0
    hardware_specified = []
    
    for pattern, hw_name in HARDWARE_PATTERNS.items():
        if re.search(pattern, paper.abstract, re.IGNORECASE):
            if hw_name not in hardware_specified:
                hardware_specified.append(hw_name)
                hardware_score += 5
    
    hardware_score = min(15, hardware_score)
    
    # 4. Tested at scale (15 points max)
    scale_score = 0
    scale_indicators = []
    tested_at_scale = False
    
    for pattern, check_fn in SCALE_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                if check_fn(match):
                    indicator = match.group(0)
                    if indicator not in scale_indicators:
                        scale_indicators.append(indicator)
                        scale_score += 5
                        tested_at_scale = True
            except (ValueError, IndexError):
                continue
    
    scale_score = min(15, scale_score)
    
    # 5. Compares to baselines (15 points max)
    baseline_score = 0
    baselines_found = []
    
    for baseline in BASELINE_SYSTEMS:
        if baseline in text:
            if baseline not in baselines_found:
                baselines_found.append(baseline)
                baseline_score += 5
    
    baseline_score = min(15, baseline_score)
    
    # 6. Real workloads (10 points max)
    workload_score = 0
    uses_real_workloads = False
    
    for pattern in REAL_WORKLOAD_PATTERNS:
        if pattern in text:
            uses_real_workloads = True
            workload_score = 10
            break
    
    # Total score
    total_score = (
        code_score + benchmark_score + hardware_score +
        scale_score + baseline_score + workload_score
    )
    
    return ProductionReadiness(
        score=round(total_score, 2),
        has_code=has_code,
        github_url=github_url,
        has_reproducible_benchmarks=has_reproducible_benchmarks,
        benchmarks_mentioned=benchmarks_mentioned,
        hardware_specified=hardware_specified,
        tested_at_scale=tested_at_scale,
        scale_indicators=scale_indicators[:5],  # Limit to 5
        compares_to_baselines=baselines_found,
        uses_real_workloads=uses_real_workloads,
    )
