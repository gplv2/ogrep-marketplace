"""
Cross-encoder reranking for improved search result ordering.

This module provides optional reranking of search results using cross-encoder
models. Cross-encoders are more accurate than bi-encoders (embeddings) because
they process query and document together, but are slower since they can't be
pre-computed.

The two-stage retrieval pattern:
1. Fast retrieval: Use embeddings + BM25 to get top 50-100 candidates
2. Slow reranking: Use cross-encoder to precisely order top 10-20

This is an optional feature requiring sentence-transformers:
    pip install "ogrep[rerank]"

Environment variables:
    OGREP_RERANK_MODEL: Cross-encoder model to use (default: BAAI/bge-reranker-v2-m3)
    OGREP_RERANK_TOPN: Number of candidates to rerank (default: 50)

Usage:
    ogrep query "where is auth" --rerank           # Enable reranking
    ogrep query "where is auth" --rerank-top 30   # Rerank top 30 candidates
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

# Default configuration
DEFAULT_RERANK_MODEL = os.environ.get("OGREP_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
DEFAULT_RERANK_TOPN = int(os.environ.get("OGREP_RERANK_TOPN", "50"))

# Try to import CrossEncoder at module level for easier testing
# Will be None if sentence-transformers not installed
try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None  # type: ignore[misc, assignment]

# Cached model instance
_reranker_model: Any = None

if TYPE_CHECKING:
    from .search import Hit


def is_reranker_available() -> bool:
    """
    Check if the reranker is available (sentence-transformers installed).

    Returns:
        True if sentence-transformers is installed and importable.
    """
    return CrossEncoder is not None


def _clear_reranker_cache() -> None:
    """Clear the cached reranker model. Used for testing."""
    global _reranker_model
    _reranker_model = None


def _get_reranker(model_name: str | None = None) -> Any:
    """
    Get or create the cached reranker model.

    The model is loaded lazily on first use and cached for subsequent calls.
    First load will download the model (~300MB for bge-reranker-v2-m3).

    Args:
        model_name: Model identifier. If None, uses OGREP_RERANK_MODEL env var
                   or default (BAAI/bge-reranker-v2-m3).

    Returns:
        CrossEncoder model instance.

    Raises:
        ImportError: If sentence-transformers is not installed.
    """
    global _reranker_model

    if _reranker_model is not None:
        return _reranker_model

    if CrossEncoder is None:
        raise ImportError(
            "Reranking requires sentence-transformers. "
            "Install with: pip install 'ogrep[rerank]'"
        )

    model = model_name or os.environ.get("OGREP_RERANK_MODEL", DEFAULT_RERANK_MODEL)
    _reranker_model = CrossEncoder(model)

    return _reranker_model


def _compute_confidence(score: float, top_score: float) -> str:
    """
    Compute confidence level for a reranked result.

    Uses relative scoring (comparing to top result) since cross-encoder
    scores have different distributions than embedding similarities.

    Args:
        score: The reranker score for this result.
        top_score: The highest reranker score in the result set.

    Returns:
        Confidence level: "high", "medium", "low", or "very_low".
    """
    if top_score <= 0:
        return "very_low"

    ratio = score / top_score

    if ratio >= 0.90:
        return "high"
    elif ratio >= 0.75:
        return "medium"
    elif ratio >= 0.50:
        return "low"
    else:
        return "very_low"


@dataclass
class RerankedHit:
    """
    A search result after reranking.

    This is a new Hit with updated score and confidence from the cross-encoder.
    """

    score: float
    path: str
    start_line: int
    end_line: int
    text: str
    chunk_id: int
    chunk_index: int
    confidence: str


def rerank_results(
    query: str,
    hits: list[Any],
    top_n: int | None = None,
    model_name: str | None = None,
) -> list[Any]:
    """
    Rerank search results using a cross-encoder model.

    Takes the top N candidates from initial retrieval and reorders them
    based on cross-encoder relevance scores. Cross-encoders process
    (query, document) pairs together for more accurate relevance judgment.

    Args:
        query: The search query string.
        hits: List of Hit objects from initial search.
        top_n: Number of candidates to rerank (default: OGREP_RERANK_TOPN or 50).
        model_name: Optional model override (default: OGREP_RERANK_MODEL).

    Returns:
        List of Hit objects reordered by cross-encoder scores, with updated
        score and confidence fields.

    Example:
        >>> hits = search(db_path, query, mode="hybrid", limit=50)
        >>> reranked = rerank_results(query, hits, top_n=50)
        >>> top_10 = reranked[:10]  # Best 10 results after reranking
    """
    if not hits:
        return []

    # Determine how many to rerank
    n = top_n if top_n is not None else DEFAULT_RERANK_TOPN
    candidates = hits[:n]

    if len(candidates) == 0:
        return []

    # Get reranker model
    reranker = _get_reranker(model_name)

    # Create (query, document) pairs for cross-encoder
    pairs = [(query, hit.text) for hit in candidates]

    # Get cross-encoder scores
    scores = reranker.predict(pairs)

    # Convert to list if numpy array
    if hasattr(scores, "tolist"):
        scores = scores.tolist()

    # Find top score for confidence calculation
    top_score = max(scores) if scores else 0.0

    # Create reranked hits with updated scores
    scored_hits = []
    for hit, score in zip(candidates, scores):
        confidence = _compute_confidence(score, top_score)

        # Create new hit with updated score and confidence
        reranked = RerankedHit(
            score=float(score),
            path=hit.path,
            start_line=hit.start_line,
            end_line=hit.end_line,
            text=hit.text,
            chunk_id=hit.chunk_id,
            chunk_index=hit.chunk_index,
            confidence=confidence,
        )
        scored_hits.append((score, reranked))

    # Sort by reranker score (descending)
    scored_hits.sort(key=lambda x: x[0], reverse=True)

    # Return just the hits
    return [hit for _, hit in scored_hits]
