"""Topic relevance scoring for LLM inference papers."""

import re
from typing import Optional

from .models import Paper
from .scoring import TopicRelevance


# LLM Inference Topic Taxonomy
# Each category has keywords with weights (higher = more relevant)
KEYWORD_TAXONOMY = {
    "quantization": {
        # High weight (3)
        "quantization": 3, "int8": 3, "int4": 3, "fp8": 3, "fp4": 3,
        "awq": 3, "gptq": 3, "gguf": 3, "ggml": 3, "exl2": 3,
        "bits": 2, "bitsandbytes": 3, "qat": 2, "ptq": 2,
        # Medium weight (2)
        "weight quantization": 2, "activation quantization": 2,
        "quantized": 2, "low-bit": 2, "low bit": 2,
        "mixed precision": 2, "mixed-precision": 2,
    },
    "kv_cache": {
        # High weight (3)
        "kv cache": 3, "kv-cache": 3, "key-value cache": 3,
        "paged attention": 3, "pagedattention": 3,
        "flash attention": 3, "flashattention": 3, "flash-attention": 3,
        "flash decoding": 3, "flashdecoding": 3,
        # Medium weight (2)
        "cache eviction": 2, "cache compression": 2,
        "attention optimization": 2, "memory-efficient attention": 2,
        "sliding window": 2, "grouped query attention": 2, "gqa": 2,
        "multi-query attention": 2, "mqa": 2,
    },
    "speculative_decoding": {
        # High weight (3)
        "speculative decoding": 3, "speculative-decoding": 3,
        "draft model": 3, "assisted generation": 3,
        "lookahead decoding": 3, "medusa": 3,
        "parallel decoding": 2, "speculative sampling": 3,
        # Medium weight (2)
        "early exit": 2, "token prediction": 2,
    },
    "batching": {
        # High weight (3)
        "continuous batching": 3, "dynamic batching": 3,
        "iteration-level batching": 3, "orca": 3,
        "request scheduling": 2, "batch scheduling": 2,
        # Medium weight (2)
        "batching strategy": 2, "batch size": 2,
        "concurrent requests": 2, "request queue": 2,
    },
    "parallelism": {
        # High weight (3)
        "tensor parallel": 3, "tensor parallelism": 3,
        "pipeline parallel": 3, "pipeline parallelism": 3,
        "sequence parallel": 3, "sequence parallelism": 3,
        "model parallel": 3, "model parallelism": 3,
        # Medium weight (2)
        "distributed inference": 2, "model sharding": 2,
        "multi-gpu": 2, "multi gpu": 2, "multi-node": 2,
        "data parallel": 2,
    },
    "memory_optimization": {
        # High weight (3)
        "memory optimization": 3, "memory-efficient": 3,
        "activation checkpointing": 3, "gradient checkpointing": 3,
        "offloading": 3, "cpu offload": 3, "gpu offload": 3,
        "memory footprint": 2, "memory reduction": 2,
        # Medium weight (2)
        "oom": 2, "out of memory": 2, "memory pressure": 2,
        "memory management": 2, "memory allocation": 2,
    },
    "serving": {
        # High weight (3)
        "inference server": 3, "serving system": 3, "serving framework": 3,
        "vllm": 3, "tensorrt-llm": 3, "tensorrt llm": 3, "trt-llm": 3,
        "triton inference": 3, "text generation inference": 3, "tgi": 3,
        "sglang": 3, "lmdeploy": 3,
        # Medium weight (2)
        "throughput optimization": 2, "latency optimization": 2,
        "ttft": 2, "time to first token": 2,
        "tokens per second": 2, "tps": 2,
        "request rate": 2, "qps": 2, "queries per second": 2,
    },
    "efficiency": {
        # High weight (3)
        "inference optimization": 3, "inference efficiency": 3,
        "efficient inference": 3, "fast inference": 3,
        "inference acceleration": 3, "kernel optimization": 3,
        "cuda kernel": 2, "triton kernel": 2,
        # Medium weight (2)
        "speedup": 2, "faster": 2, "efficient": 2,
        "performance optimization": 2, "compute efficiency": 2,
    },
}

# Topic categories in order of specificity (more specific = higher priority)
CATEGORY_PRIORITY = [
    "speculative_decoding",
    "kv_cache",
    "quantization",
    "batching",
    "parallelism",
    "memory_optimization",
    "serving",
    "efficiency",
]


def compute_topic_relevance(
    paper: Paper,
    embedding_store=None,
    full_text: Optional[str] = None,
) -> TopicRelevance:
    """
    Compute topic relevance score for a paper.
    
    Combines keyword matching (fast) with optional embedding similarity (accurate).
    
    Args:
        paper: Paper object to score
        embedding_store: Optional EmbeddingsStore for semantic similarity
        full_text: Optional full paper text (extracted from PDF)
        
    Returns:
        TopicRelevance object with scores and matched keywords
    """
    # Use full text if provided, otherwise just title + abstract
    if full_text:
        text = full_text.lower()
    else:
        text = f"{paper.title} {paper.abstract}".lower()
    
    # 1. Keyword matching
    matched_keywords = []
    category_scores = {cat: 0 for cat in KEYWORD_TAXONOMY}
    total_keyword_score = 0
    
    for category, keywords in KEYWORD_TAXONOMY.items():
        for keyword, weight in keywords.items():
            # Use word boundary matching for short keywords
            if len(keyword) <= 4:
                pattern = rf"\b{re.escape(keyword)}\b"
                if re.search(pattern, text, re.IGNORECASE):
                    matched_keywords.append(keyword)
                    category_scores[category] += weight
                    total_keyword_score += weight
            else:
                if keyword in text:
                    matched_keywords.append(keyword)
                    category_scores[category] += weight
                    total_keyword_score += weight
    
    # Remove duplicates while preserving order
    matched_keywords = list(dict.fromkeys(matched_keywords))
    
    # 2. Determine primary topic category
    primary_category = ""
    max_category_score = 0
    for cat in CATEGORY_PRIORITY:
        if category_scores[cat] > max_category_score:
            max_category_score = category_scores[cat]
            primary_category = cat
    
    # 3. Normalize keyword score to 0-100
    # Max expected score: ~20 (5-6 highly relevant keywords)
    keyword_score = min(100, (total_keyword_score / 20) * 100)
    
    # 4. Embedding similarity (if available)
    embedding_similarity = 0.0
    if embedding_store and hasattr(embedding_store, 'search_golden_set'):
        try:
            # Search against golden set of known-good papers
            similarity = embedding_store.search_golden_set(
                f"{paper.title} {paper.abstract}"
            )
            embedding_similarity = similarity
        except Exception:
            pass
    
    # 5. Combine scores
    # If embedding available: 40% keyword, 60% embedding
    # If no embedding: 100% keyword
    if embedding_similarity > 0:
        final_score = 0.4 * keyword_score + 0.6 * (embedding_similarity * 100)
    else:
        final_score = keyword_score
    
    return TopicRelevance(
        score=round(final_score, 2),
        matched_keywords=matched_keywords,
        topic_category=primary_category,
        embedding_similarity=round(embedding_similarity, 4),
    )


def get_topic_categories() -> list[str]:
    """Get list of all topic categories."""
    return list(KEYWORD_TAXONOMY.keys())


def get_category_keywords(category: str) -> dict[str, int]:
    """Get keywords and weights for a specific category."""
    return KEYWORD_TAXONOMY.get(category, {})
