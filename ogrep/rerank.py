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

import io
import os
import sys
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

# Default configuration
DEFAULT_RERANK_MODEL = os.environ.get("OGREP_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
DEFAULT_RERANK_TOPN = int(os.environ.get("OGREP_RERANK_TOPN", "50"))

# Lazy-loaded CrossEncoder class (imported on first use to capture CUDA warnings)
# Will be None if sentence-transformers not installed
_CrossEncoder: Any = None
_crossencoder_import_attempted: bool = False

# Cached model instance
_reranker_model: Any = None

# Captured warnings from model loading (CUDA, etc.)
_captured_warnings: list[str] = []

if TYPE_CHECKING:
    pass


@contextmanager
def _suppress_stderr_warnings():
    """
    Context manager to capture stderr output from libraries like PyTorch.

    PyTorch and other ML libraries often print warnings directly to stderr
    (e.g., CUDA initialization warnings) which can corrupt JSON output.
    This captures them so they can be reported in a structured way.

    Yields:
        A StringIO object containing captured stderr.
    """
    old_stderr = sys.stderr
    captured = io.StringIO()

    # Also suppress Python warnings that might go to stderr
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        try:
            sys.stderr = captured
            yield captured
        finally:
            sys.stderr = old_stderr


def _parse_captured_output(captured_text: str) -> list[str]:
    """
    Parse captured stderr output into clean warning messages.

    Args:
        captured_text: Raw text captured from stderr.

    Returns:
        List of cleaned warning messages.
    """
    warnings_list = []
    if not captured_text:
        return warnings_list

    for line in captured_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Extract the actual warning message if it's a Python warning format
        if "UserWarning:" in line:
            # Extract message after UserWarning:
            idx = line.find("UserWarning:")
            msg = line[idx + len("UserWarning:") :].strip()
            if msg:
                warnings_list.append(msg)
        elif "Warning:" in line or "warning:" in line.lower():
            warnings_list.append(line)
        elif not line.startswith("return ") and "torch" not in line.lower():
            # Skip internal code lines but keep other messages
            if not line.startswith("_") and "site-packages" not in line:
                warnings_list.append(line)

    return warnings_list


def _lazy_import_crossencoder() -> Any:
    """
    Lazily import CrossEncoder, capturing any CUDA warnings during import.

    This is called once to import sentence_transformers.CrossEncoder.
    The import is deferred until first use so we can capture stderr during
    the import (which is when PyTorch's CUDA initialization warning occurs).

    Returns:
        CrossEncoder class or None if not installed.
    """
    global _CrossEncoder, _crossencoder_import_attempted, _captured_warnings

    if _crossencoder_import_attempted:
        return _CrossEncoder

    _crossencoder_import_attempted = True

    # Capture stderr during import - this is when CUDA warnings occur
    with _suppress_stderr_warnings() as captured:
        try:
            from sentence_transformers import CrossEncoder

            _CrossEncoder = CrossEncoder
        except ImportError:
            _CrossEncoder = None

    # Parse any warnings from the import
    captured_text = captured.getvalue().strip()
    _captured_warnings.extend(_parse_captured_output(captured_text))

    return _CrossEncoder


def get_captured_warnings() -> list[str]:
    """
    Get warnings captured during reranker initialization.

    Returns:
        List of warning messages (may be empty).
    """
    return _captured_warnings.copy()


def clear_captured_warnings() -> None:
    """Clear captured warnings. Useful after reporting them."""
    global _captured_warnings
    _captured_warnings = []


def is_reranker_available() -> bool:
    """
    Check if the reranker is available (sentence-transformers installed).

    Returns:
        True if sentence-transformers is installed and importable.
    """
    CrossEncoder = _lazy_import_crossencoder()
    return CrossEncoder is not None


def _clear_reranker_cache() -> None:
    """Clear the cached reranker model. Used for testing."""
    global _reranker_model, _captured_warnings, _CrossEncoder, _crossencoder_import_attempted
    _reranker_model = None
    _captured_warnings = []
    # Note: Don't reset _CrossEncoder/_crossencoder_import_attempted in production
    # as re-importing won't trigger new warnings. Only reset in tests.


def _clear_all_state() -> None:
    """Clear all state including import cache. For testing only."""
    global _reranker_model, _captured_warnings, _CrossEncoder, _crossencoder_import_attempted
    _reranker_model = None
    _captured_warnings = []
    _CrossEncoder = None
    _crossencoder_import_attempted = False


def _get_reranker(model_name: str | None = None) -> Any:
    """
    Get or create the cached reranker model.

    The model is loaded lazily on first use and cached for subsequent calls.
    First load will download the model (~300MB for bge-reranker-v2-m3).

    Any warnings (e.g., CUDA initialization) are captured and can be retrieved
    via get_captured_warnings() for structured output.

    Args:
        model_name: Model identifier. If None, uses OGREP_RERANK_MODEL env var
                   or default (BAAI/bge-reranker-v2-m3).

    Returns:
        CrossEncoder model instance.

    Raises:
        ImportError: If sentence-transformers is not installed.
    """
    global _reranker_model, _captured_warnings

    if _reranker_model is not None:
        return _reranker_model

    CrossEncoder = _lazy_import_crossencoder()

    if CrossEncoder is None:
        raise ImportError(
            "Reranking requires sentence-transformers. Install with: pip install 'ogrep[rerank]'"
        )

    model = model_name or os.environ.get("OGREP_RERANK_MODEL", DEFAULT_RERANK_MODEL)

    # Capture any stderr output (CUDA warnings, etc.) during model instantiation
    with _suppress_stderr_warnings() as captured:
        _reranker_model = CrossEncoder(model)

    # Parse any additional warnings from model instantiation
    captured_text = captured.getvalue().strip()
    _captured_warnings.extend(_parse_captured_output(captured_text))

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
    for hit, score in zip(candidates, scores, strict=False):
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
