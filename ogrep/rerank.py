"""
Cross-encoder reranking for improved search result ordering.

This module provides optional reranking of search results using cross-encoder
models. Cross-encoders are more accurate than bi-encoders (embeddings) because
they process query and document together, but are slower since they can't be
pre-computed.

The two-stage retrieval pattern:
1. Fast retrieval: Use embeddings + BM25 to get top 50-100 candidates
2. Slow reranking: Use cross-encoder to precisely order top 10-20

Two backend options are available:

1. FlashRank (default, lightweight, parallel-safe):
    pip install "ogrep[rerank-light]"
    Models: flashrank (default, 4MB), flashrank:mini (50MB)
    Note: Uses ONNX runtime, no PyTorch overhead, safe for parallel use.
    Recommended for local embeddings (Nomic) - improves MRR by ~16%.

2. sentence-transformers (higher quality, heavier):
    pip install "ogrep[rerank]"
    Models: bge-m3 (300MB), minilm (90MB)
    Note: Uses file-based locking to prevent OOM in parallel sessions.
    Warning: bge-m3 is slow on CPU (~30s/query). Not recommended without GPU.

Environment variables:
    OGREP_RERANK_MODEL: Reranker model or alias (default: flashrank)
    OGREP_RERANK_TOPN: Number of candidates to rerank (default: 50)
    OGREP_RERANK_LOCK: Lock file path for parallel safety (sentence-transformers only)
    OGREP_RERANK_LOCK_TIMEOUT: Lock timeout in seconds (default: 120)

Usage:
    ogrep query "where is auth" --rerank                       # Default (flashrank)
    ogrep query "where is auth" --rerank-model bge-m3          # Heavy PyTorch (GPU only)
    ogrep query "where is auth" --rerank-model flashrank:mini  # Medium ONNX
    ogrep query "where is auth" --rerank-model minilm          # Smaller PyTorch
"""

from __future__ import annotations

import fcntl
import io
import os
import sys
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

# =============================================================================
# Model Configuration
# =============================================================================

# Model aliases map user-friendly names to actual model identifiers
# Sentence-transformers models (PyTorch backend)
SENTENCE_TRANSFORMERS_ALIASES = {
    "bge-m3": "BAAI/bge-reranker-v2-m3",
    "minilm": "cross-encoder/ms-marco-MiniLM-L6-v2",
}

# FlashRank models (ONNX backend - lightweight, parallel-safe)
FLASHRANK_ALIASES = {
    "flashrank": "ms-marco-TinyBERT-L-2-v2",
    "flashrank:tiny": "ms-marco-TinyBERT-L-2-v2",
    "flashrank:mini": "ms-marco-MiniLM-L-12-v2",
}

# Voyage AI models (REST API backend - code-optimized reranking)
VOYAGE_RERANK_ALIASES = {
    "voyage": "rerank-2.5",
    "voyage:lite": "rerank-2.5-lite",
    "voyage:2": "rerank-2",
}

# Combined aliases for model resolution
RERANK_MODEL_ALIASES = {
    **SENTENCE_TRANSFORMERS_ALIASES,
    **FLASHRANK_ALIASES,
    **VOYAGE_RERANK_ALIASES,
}

# Default configuration
DEFAULT_RERANK_MODEL = "flashrank"  # Lightweight, parallel-safe, best for local embeddings
DEFAULT_RERANK_TOPN = int(os.environ.get("OGREP_RERANK_TOPN", "50"))

# Lock configuration - prevents multiple processes from loading the ~300MB model simultaneously
_lock_env = os.environ.get("OGREP_RERANK_LOCK")
RERANK_LOCK_PATH = (
    Path(os.path.expanduser(_lock_env)) if _lock_env else Path.home() / ".cache" / "ogrep" / "rerank.lock"
)
RERANK_LOCK_TIMEOUT = float(os.environ.get("OGREP_RERANK_LOCK_TIMEOUT", "120"))  # seconds

# =============================================================================
# Backend Detection
# =============================================================================


def _is_flashrank_model(model_name: str) -> bool:
    """Check if the model name indicates a FlashRank backend."""
    return model_name.startswith("flashrank") or model_name in FLASHRANK_ALIASES.values()


def _is_voyage_rerank_model(model_name: str) -> bool:
    """Check if the model name indicates a Voyage AI reranking backend."""
    return (
        model_name.startswith("voyage")
        or model_name in VOYAGE_RERANK_ALIASES
        or model_name in VOYAGE_RERANK_ALIASES.values()
    )


def _is_sentence_transformers_model(model_name: str) -> bool:
    """Check if the model name indicates a sentence-transformers backend."""
    # If it's a FlashRank or Voyage model, it's not sentence-transformers
    if _is_flashrank_model(model_name) or _is_voyage_rerank_model(model_name):
        return False
    # Otherwise assume sentence-transformers (includes full HuggingFace paths)
    return True


def _resolve_model_name(model_name: str) -> str:
    """
    Resolve a model alias to its actual model identifier.

    Args:
        model_name: User-provided model name or alias.

    Returns:
        Actual model identifier to use with the backend.
    """
    return RERANK_MODEL_ALIASES.get(model_name, model_name)


def is_flashrank_available() -> bool:
    """Check if FlashRank is installed and importable."""
    try:
        import flashrank  # noqa: F401

        return True
    except ImportError:
        return False


def is_sentence_transformers_available() -> bool:
    """Check if sentence-transformers is installed and importable."""
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


def is_voyage_rerank_available() -> bool:
    """Check if Voyage AI reranking is available (SDK installed + API key set)."""
    try:
        import voyageai  # noqa: F401

        return os.environ.get("VOYAGE_API_KEY") is not None
    except ImportError:
        return False


# =============================================================================
# Lazy-loaded State
# =============================================================================

# Lazy-loaded CrossEncoder class (imported on first use to capture CUDA warnings)
# Will be None if sentence-transformers not installed
_CrossEncoder: Any = None
_crossencoder_import_attempted: bool = False

# Cached model instances (one per backend)
_reranker_model: Any = None  # sentence-transformers CrossEncoder
_flashrank_ranker: Any = None  # FlashRank Ranker
_flashrank_model_name: str | None = None  # Track which FlashRank model is loaded
_voyage_rerank_client: Any = None  # Voyage AI Client for reranking

# Captured warnings from model loading (CUDA, etc.)
_captured_warnings: list[str] = []

if TYPE_CHECKING:
    pass


class RerankLockTimeout(Exception):
    """Raised when unable to acquire rerank lock within timeout."""

    pass


@contextmanager
def _rerank_lock(timeout: float | None = None):
    """
    Context manager for exclusive access to reranking resources.

    Prevents multiple processes from loading the ~300MB cross-encoder model
    simultaneously, which can cause OOM errors. Uses file-based locking
    with fcntl (Unix/macOS).

    If the lock file cannot be created (e.g., read-only filesystem, permissions),
    the context manager proceeds without locking (with a warning).

    Args:
        timeout: Maximum seconds to wait for lock. None uses RERANK_LOCK_TIMEOUT.

    Raises:
        RerankLockTimeout: If lock cannot be acquired within timeout.

    Example:
        >>> with _rerank_lock(timeout=60):
        ...     # Only one process can be here at a time
        ...     results = reranker.predict(pairs)
    """
    global _captured_warnings

    if timeout is None:
        timeout = RERANK_LOCK_TIMEOUT

    # Try to ensure lock directory exists
    lock_file = None
    acquired = False

    try:
        RERANK_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Read-only filesystem or permission denied - proceed without lock
        _captured_warnings.append(
            f"Cannot create lock directory {RERANK_LOCK_PATH.parent}. "
            "Proceeding without parallel protection."
        )
        yield
        return

    try:
        lock_file = open(RERANK_LOCK_PATH, "w")
    except OSError as e:
        # Cannot create lock file - proceed without lock
        _captured_warnings.append(
            f"Cannot create lock file {RERANK_LOCK_PATH}: {e}. "
            "Proceeding without parallel protection."
        )
        yield
        return

    try:
        start_time = time.monotonic()

        while True:
            try:
                # Try to acquire exclusive lock (non-blocking)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except (OSError, BlockingIOError):
                # Lock is held by another process
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    raise RerankLockTimeout(
                        f"Rerank lock timeout after {timeout:.1f}s. "
                        "Another process may be loading the cross-encoder model."
                    ) from None  # Intentional - not chaining from the BlockingIOError
                # Wait and retry
                time.sleep(0.5)

        yield

    finally:
        if acquired and lock_file is not None:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass  # Best effort unlock
        if lock_file is not None:
            try:
                lock_file.close()
            except OSError:
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


def get_available_backends() -> dict[str, Any]:
    """
    Get information about available reranking backends.

    Returns:
        Dictionary with backend availability and model info:
        {
            "sentence_transformers": {
                "available": bool,
                "install": str,
                "models": [{"alias": str, "name": str, "size": str}, ...],
            },
            "flashrank": {
                "available": bool,
                "install": str,
                "models": [{"alias": str, "name": str, "size": str}, ...],
            },
            "voyage_ai": {
                "available": bool,
                "install": str,
                "models": [{"alias": str, "name": str, "context": str}, ...],
            },
            "default_model": str,
        }
    """
    return {
        "sentence_transformers": {
            "available": is_sentence_transformers_available(),
            "install": "pip install 'ogrep[rerank]'",
            "models": [
                {
                    "alias": "bge-m3",
                    "name": "BAAI/bge-reranker-v2-m3",
                    "size": "~300MB",
                    "context": "8K tokens",
                    "note": "Best quality, needs lock for parallel safety",
                },
                {
                    "alias": "minilm",
                    "name": "cross-encoder/ms-marco-MiniLM-L6-v2",
                    "size": "~90MB",
                    "context": "512 tokens",
                    "note": "Smaller, faster, needs lock for parallel safety",
                },
            ],
        },
        "flashrank": {
            "available": is_flashrank_available(),
            "install": "pip install 'ogrep[rerank-light]'",
            "models": [
                {
                    "alias": "flashrank",
                    "name": "ms-marco-TinyBERT-L-2-v2",
                    "size": "~4MB",
                    "context": "512 tokens",
                    "note": "Lightweight ONNX, parallel-safe",
                },
                {
                    "alias": "flashrank:mini",
                    "name": "ms-marco-MiniLM-L-12-v2",
                    "size": "~50MB",
                    "context": "512 tokens",
                    "note": "Better quality ONNX, parallel-safe",
                },
            ],
        },
        "voyage_ai": {
            "available": is_voyage_rerank_available(),
            "install": "pip install 'ogrep[voyage]' (+ set VOYAGE_API_KEY)",
            "models": [
                {
                    "alias": "voyage",
                    "name": "rerank-2.5",
                    "context": "32K tokens",
                    "note": "Code-optimized, instruction-following (REST API)",
                },
                {
                    "alias": "voyage:lite",
                    "name": "rerank-2.5-lite",
                    "context": "32K tokens",
                    "note": "Faster, cheaper (REST API)",
                },
                {
                    "alias": "voyage:2",
                    "name": "rerank-2",
                    "context": "16K tokens",
                    "note": "Previous generation (REST API)",
                },
            ],
        },
        "default_model": DEFAULT_RERANK_MODEL,
    }


def is_reranker_available(model_name: str | None = None) -> bool:
    """
    Check if reranking is available for the specified model.

    Args:
        model_name: Model name or alias. If None, checks if any backend is available.

    Returns:
        True if the required backend is installed and importable.
    """
    if model_name is None:
        # Check if any backend is available
        return (
            is_flashrank_available()
            or is_sentence_transformers_available()
            or is_voyage_rerank_available()
        )

    # Check specific backend based on model
    if _is_voyage_rerank_model(model_name):
        return is_voyage_rerank_available()
    elif _is_flashrank_model(model_name):
        return is_flashrank_available()
    else:
        CrossEncoder = _lazy_import_crossencoder()
        return CrossEncoder is not None


def _clear_reranker_cache() -> None:
    """Clear the cached reranker model. Used for testing."""
    global _reranker_model, _flashrank_ranker, _flashrank_model_name
    global _captured_warnings, _CrossEncoder, _crossencoder_import_attempted
    _reranker_model = None
    _flashrank_ranker = None
    _flashrank_model_name = None
    _captured_warnings = []
    # Note: Don't reset _CrossEncoder/_crossencoder_import_attempted in production
    # as re-importing won't trigger new warnings. Only reset in tests.


def _clear_all_state() -> None:
    """Clear all state including import cache. For testing only."""
    global _reranker_model, _flashrank_ranker, _flashrank_model_name
    global _captured_warnings, _CrossEncoder, _crossencoder_import_attempted
    _reranker_model = None
    _flashrank_ranker = None
    _flashrank_model_name = None
    _captured_warnings = []
    _CrossEncoder = None
    _crossencoder_import_attempted = False


def _get_reranker(model_name: str | None = None) -> Any:
    """
    Get or create the cached sentence-transformers reranker model.

    The model is loaded lazily on first use and cached for subsequent calls.
    First load will download the model (~300MB for bge-reranker-v2-m3).

    Any warnings (e.g., CUDA initialization) are captured and can be retrieved
    via get_captured_warnings() for structured output.

    Args:
        model_name: Model name or alias. If None, uses OGREP_RERANK_MODEL env var
                   or default (bge-m3).

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

    # Resolve alias to actual model identifier
    actual_model = _resolve_model_name(model)

    # Capture any stderr output (CUDA warnings, etc.) during model instantiation
    with _suppress_stderr_warnings() as captured:
        _reranker_model = CrossEncoder(actual_model)

    # Parse any additional warnings from model instantiation
    captured_text = captured.getvalue().strip()
    _captured_warnings.extend(_parse_captured_output(captured_text))

    return _reranker_model


def _get_flashrank_reranker(model_name: str) -> Any:
    """
    Get or create the cached FlashRank reranker model.

    FlashRank uses ONNX runtime, which is much lighter than PyTorch
    (~50MB vs ~500MB overhead) and is safe for parallel use without locking.

    Args:
        model_name: Model name or alias (e.g., "flashrank", "flashrank:mini").

    Returns:
        FlashRank Ranker instance.

    Raises:
        ImportError: If flashrank is not installed.
    """
    global _flashrank_ranker, _flashrank_model_name, _captured_warnings

    # Resolve alias to actual model name
    actual_model = _resolve_model_name(model_name)

    # Check if we need to load a different model
    if _flashrank_ranker is not None and _flashrank_model_name == actual_model:
        return _flashrank_ranker

    # Import FlashRank
    try:
        from flashrank import Ranker
    except ImportError as e:
        raise ImportError(
            "FlashRank reranking requires the flashrank package. "
            "Install with: pip install 'ogrep[rerank-light]'"
        ) from e

    # Capture any stderr output during model load
    with _suppress_stderr_warnings() as captured:
        _flashrank_ranker = Ranker(model_name=actual_model)
        _flashrank_model_name = actual_model

    # Parse any warnings from model instantiation
    captured_text = captured.getvalue().strip()
    _captured_warnings.extend(_parse_captured_output(captured_text))

    return _flashrank_ranker


def _flashrank_predict(ranker: Any, query: str, texts: list[str]) -> list[float]:
    """
    Get reranking scores from FlashRank.

    Args:
        ranker: FlashRank Ranker instance.
        query: The search query.
        texts: List of document texts to score.

    Returns:
        List of scores in the SAME ORDER as input texts.
    """
    from flashrank import RerankRequest

    # Create passages with IDs to track original order
    passages = [{"id": i, "text": t} for i, t in enumerate(texts)]

    # Rerank
    request = RerankRequest(query=query, passages=passages)
    results = ranker.rerank(request)

    # FlashRank returns results sorted by score descending
    # We need to map back to original order using the id field
    # Convert to Python float (FlashRank returns numpy float32 which isn't JSON serializable)
    scores = [0.0] * len(texts)
    for r in results:
        idx = r["id"]
        scores[idx] = float(r["score"])

    return scores


def _get_voyage_reranker() -> Any:
    """
    Get or create the cached Voyage AI client for reranking.

    Voyage AI provides code-optimized reranking via REST API.
    Unlike local models, this calls the Voyage AI API.

    Environment variables:
        VOYAGE_API_KEY: Required API key.
        OGREP_VOYAGE_TIMEOUT: Request timeout in seconds (default: 120).
        OGREP_VOYAGE_RETRIES: Max retries on failure (default: 2).

    Returns:
        Voyage AI Client instance.

    Raises:
        ImportError: If voyageai is not installed.
        ValueError: If VOYAGE_API_KEY is not set.
    """
    global _voyage_rerank_client, _captured_warnings

    if _voyage_rerank_client is not None:
        return _voyage_rerank_client

    try:
        import voyageai
    except ImportError as e:
        raise ImportError(
            "Voyage AI reranking requires the voyageai package. "
            "Install with: pip install 'ogrep[voyage]'"
        ) from e

    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        raise ValueError(
            "VOYAGE_API_KEY environment variable is not set. "
            "Get your API key from https://dash.voyageai.com/"
        )

    # Get timeout and retry settings (same as embed.py)
    timeout_str = os.environ.get("OGREP_VOYAGE_TIMEOUT")
    timeout = float(timeout_str) if timeout_str else 120.0
    retries_str = os.environ.get("OGREP_VOYAGE_RETRIES")
    max_retries = int(retries_str) if retries_str else 2

    _voyage_rerank_client = voyageai.Client(
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries,
    )
    return _voyage_rerank_client


def _voyage_rerank_predict(query: str, texts: list[str], model: str) -> list[float]:
    """
    Get reranking scores from Voyage AI API.

    Args:
        query: The search query.
        texts: List of document texts to score.
        model: Model name or alias (e.g., "voyage", "rerank-2.5").

    Returns:
        List of scores in the SAME ORDER as input texts.
    """
    client = _get_voyage_reranker()

    # Resolve alias to actual model name
    actual_model = VOYAGE_RERANK_ALIASES.get(model, model)

    # Call Voyage rerank API with timing
    start_time = time.time()
    result = client.rerank(
        query=query,
        documents=texts,
        model=actual_model,
    )
    elapsed = time.time() - start_time

    # Warn on slow requests (>10s for reranking is unusual)
    if elapsed > 10:
        print(
            f"Warning: Voyage rerank API took {elapsed:.1f}s for {len(texts)} documents",
            file=sys.stderr,
        )

    # Voyage returns results with index and relevance_score
    # Map scores back to original order
    scores = [0.0] * len(texts)
    for r in result.results:
        scores[r.index] = float(r.relevance_score)

    return scores


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
    confidence_details: Any = None  # Preserved from original hit for compatibility


def rerank_results(
    query: str,
    hits: list[Any],
    top_n: int | None = None,
    model_name: str | None = None,
    cache_path: Any | None = None,
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
        cache_path: Path to cache.sqlite for L3 caching (optional).

    Returns:
        List of Hit objects reordered by cross-encoder scores, with updated
        score and confidence fields.

    Note:
        L3 caching is content-addressable: results are cached based on
        the actual text content of chunks, not their IDs. This means
        cached results survive file moves and reindexing as long as the
        text content remains the same.

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

    # Determine model: CLI flag > env var > default
    model = model_name or os.environ.get("OGREP_RERANK_MODEL", DEFAULT_RERANK_MODEL)

    # Detect which backend to use based on model name
    use_voyage = _is_voyage_rerank_model(model)
    use_flashrank = _is_flashrank_model(model)

    # L3 Cache setup
    cache_con = None
    cache_enabled = cache_path is not None and not os.environ.get("OGREP_CACHE_DISABLED")
    chunk_hashes: list[str] = []

    if cache_enabled:
        import hashlib

        from .cache import (
            connect_cache,
            get_rerank_results,
            log_cache_event,
            set_rerank_results,
        )

        cache_con = connect_cache(cache_path)

        # Compute content-addressable chunk hashes
        chunk_hashes = [hashlib.sha256(hit.text.encode()).hexdigest()[:16] for hit in candidates]

        # Check L3 cache
        l3_result = get_rerank_results(cache_con, query, chunk_hashes, model, n)
        if l3_result.hit:
            # Cache hit - reconstruct reranked hits from cached scores
            cached_scores = l3_result.data  # List of (chunk_id, score)

            # Build chunk_id to candidate lookup
            candidate_lookup = {hit.chunk_id: hit for hit in candidates}

            # Get top score for confidence
            top_score = max(s for _, s in cached_scores) if cached_scores else 0.0

            reranked_hits = []
            for chunk_id, score in cached_scores:
                if chunk_id in candidate_lookup:
                    hit = candidate_lookup[chunk_id]
                    confidence = _compute_confidence(score, top_score)
                    reranked = RerankedHit(
                        score=float(score),
                        path=hit.path,
                        start_line=hit.start_line,
                        end_line=hit.end_line,
                        text=hit.text,
                        chunk_id=hit.chunk_id,
                        chunk_index=hit.chunk_index,
                        confidence=confidence,
                        confidence_details=getattr(hit, "confidence_details", None),
                    )
                    reranked_hits.append(reranked)

            log_cache_event(cache_con, "L3", "hit", time_saved_ms=l3_result.time_saved_ms)
            return reranked_hits

    # Route to appropriate backend
    if use_voyage:
        # Voyage AI path - REST API, no lock needed
        if not is_voyage_rerank_available():
            raise ImportError(
                "Voyage AI not available. Install with: pip install 'ogrep[voyage]' "
                "and set VOYAGE_API_KEY environment variable."
            )
        texts = [hit.text for hit in candidates]
        scores = _voyage_rerank_predict(query, texts, model)
    elif use_flashrank:
        # FlashRank path - no lock needed (ONNX is parallel-safe)
        if not is_flashrank_available():
            raise ImportError(
                "FlashRank not installed. Install with: pip install 'ogrep[rerank-light]'"
            )
        ranker = _get_flashrank_reranker(model)
        texts = [hit.text for hit in candidates]
        scores = _flashrank_predict(ranker, query, texts)
    else:
        # Sentence-transformers path - needs lock to prevent OOM
        # The ~300MB cross-encoder model can cause OOM if multiple processes load simultaneously
        try:
            with _rerank_lock():
                # Get reranker model (cache miss path)
                reranker = _get_reranker(model)

                # Create (query, document) pairs for cross-encoder
                pairs = [(query, hit.text) for hit in candidates]

                # Get cross-encoder scores
                scores = reranker.predict(pairs)

        except RerankLockTimeout as e:
            # Graceful degradation: return unreranked results with warning
            _captured_warnings.append(str(e) + " Returning unreranked results.")

            # Return candidates as-is (maintain original embedding/BM25 ranking)
            top_score = candidates[0].score if candidates else 0.0
            unreranked_hits = []
            for hit in candidates:
                confidence = _compute_confidence(hit.score, top_score)
                unreranked = RerankedHit(
                    score=float(hit.score),
                    path=hit.path,
                    start_line=hit.start_line,
                    end_line=hit.end_line,
                    text=hit.text,
                    chunk_id=hit.chunk_id,
                    chunk_index=hit.chunk_index,
                    confidence=confidence,
                    confidence_details=getattr(hit, "confidence_details", None),
                )
                unreranked_hits.append(unreranked)
            return unreranked_hits

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
            confidence_details=getattr(hit, "confidence_details", None),
        )
        scored_hits.append((score, reranked))

    # Sort by reranker score (descending)
    scored_hits.sort(key=lambda x: x[0], reverse=True)

    # L3 Cache: Store rerank results
    if cache_enabled and cache_con is not None:
        from .cache import log_cache_event, set_rerank_results

        # Store (chunk_id, score) pairs in sorted order
        results_to_cache = [(hit.chunk_id, score) for score, hit in scored_hits]
        set_rerank_results(cache_con, query, chunk_hashes, model, n, results_to_cache)
        log_cache_event(cache_con, "L3", "miss")

    # Return just the hits
    return [hit for _, hit in scored_hits]
