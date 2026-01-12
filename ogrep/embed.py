"""
Embedding module for ogrep.

Provides text embedding functionality using OpenAI's embedding API
or a local OpenAI-compatible server (like LM Studio).

Embeddings are L2-normalized for cosine similarity calculations and
stored as compact float32 binary blobs.

Requires:
    OPENAI_API_KEY environment variable (not required for local servers).

Configuration:
    OGREP_MODEL: Override default embedding model.
    OGREP_DIMENSIONS: Override default embedding dimensions.
    OGREP_BASE_URL: Use local OpenAI-compatible server (e.g., http://localhost:1234/v1).
    OGREP_BATCH_SIZE: Batch size for embedding requests (default: auto-tuned).
"""

from __future__ import annotations

import array
import math
import os
import time
from typing import Literal, overload

from openai import OpenAI

from .models import get_max_batch_size, resolve_dimensions, resolve_model

# Environment variable for batch size override
ENV_BATCH_SIZE = "OGREP_BATCH_SIZE"

# Default batch sizes for local models (small context windows)
LOCAL_BATCH_SIZES = [8, 16, 32, 64, 96]

# Minimum texts to trigger batching (below this, send all at once)
MIN_BATCH_THRESHOLD = 32

# Threshold to distinguish local vs cloud models
CLOUD_BATCH_THRESHOLD = 256


def _get_batch_sizes_for_model(max_batch: int) -> list[int]:
    """
    Generate appropriate batch sizes to test for auto-tuning.

    For local models (max_batch <= 96): use standard small sizes.
    For cloud models (max_batch > 256): use 7 steps from 64 to max.

    Args:
        max_batch: Model's maximum batch size.

    Returns:
        List of batch sizes to test.
    """
    if max_batch <= 96:
        # Local model - use standard sizes up to max
        return [bs for bs in LOCAL_BATCH_SIZES if bs <= max_batch]

    # Cloud model (OpenAI) - generate 7 steps from 64 to max
    # Using roughly geometric progression
    steps = 7
    start = 64
    end = max_batch

    if end <= start:
        return [end]

    # Generate steps: 64, then 6 more up to max
    batch_sizes = [start]
    ratio = (end / start) ** (1 / (steps - 1))

    for i in range(1, steps - 1):
        next_size = int(start * (ratio ** i))
        # Round to nice numbers (multiples of 64 or 128)
        if next_size > 512:
            next_size = (next_size // 128) * 128
        else:
            next_size = (next_size // 64) * 64
        if next_size > batch_sizes[-1]:
            batch_sizes.append(next_size)

    # Always include the max
    if batch_sizes[-1] != end:
        batch_sizes.append(end)

    return batch_sizes


def _get_default_batch_size(max_batch: int) -> int:
    """
    Get the default fallback batch size for a model.

    For local models: 16 (conservative)
    For cloud models: 200 (OpenAI benefits from larger batches)

    Args:
        max_batch: Model's maximum batch size.

    Returns:
        Default batch size.
    """
    if max_batch > CLOUD_BATCH_THRESHOLD:
        return min(200, max_batch)  # Cloud models default to 200
    return min(16, max_batch)  # Local models default to 16

# Cache for optimal batch size (per-session)
_optimal_batch_size: int | None = None


def _l2_normalize(vec: list[float]) -> list[float]:
    """
    L2-normalize a vector for cosine similarity calculations.

    Normalized vectors allow cosine similarity to be computed as a simple
    dot product, which is more efficient.

    Args:
        vec: Input vector as a list of floats.

    Returns:
        L2-normalized vector where the sum of squares equals 1.
    """
    s = 0.0
    for x in vec:
        s += x * x
    n = math.sqrt(s) if s > 0 else 1.0
    return [x / n for x in vec]


def _create_client() -> tuple[OpenAI, bool]:
    """
    Create OpenAI client, detecting if using local server.

    Returns:
        Tuple of (client, is_local) where is_local indicates local server.
    """
    base_url = os.environ.get("OGREP_BASE_URL")
    if base_url:
        api_key = os.environ.get("OPENAI_API_KEY", "lm-studio")
        return OpenAI(base_url=base_url, api_key=api_key), True
    return OpenAI(), False


def _embed_batch(
    client: OpenAI,
    texts: list[str],
    model: str,
    dimensions: int | None,
) -> tuple[list[bytes], int]:
    """
    Embed a single batch of texts.

    Args:
        client: OpenAI client instance.
        texts: List of texts to embed.
        model: Resolved model name.
        dimensions: Optional dimension override.

    Returns:
        Tuple of (embeddings, dimension).
    """
    kwargs: dict = {"input": texts, "model": model}
    if dimensions is not None:
        kwargs["dimensions"] = dimensions

    resp = client.embeddings.create(**kwargs)

    vectors: list[bytes] = []
    dim: int | None = None
    for item in resp.data:
        v = _l2_normalize(list(item.embedding))
        if dim is None:
            dim = len(v)
        arr_f = array.array("f", v)
        vectors.append(arr_f.tobytes())

    assert dim is not None
    return vectors, dim


def _find_optimal_batch_size(
    client: OpenAI,
    sample_texts: list[str],
    model: str,
    dimensions: int | None,
) -> int:
    """
    Auto-tune batch size by testing different sizes.

    Tests batch sizes and picks the one with best throughput,
    respecting the model's max_batch_size limit.

    For local models: tests [8, 16, 32, 64, 96] up to max
    For cloud models: tests 7 steps from 64 to max (e.g., 64, 128, 256, 512, 768, 1024, 2048)

    Args:
        client: OpenAI client instance.
        sample_texts: Sample texts to use for timing.
        model: Resolved model name.
        dimensions: Optional dimension override.

    Returns:
        Optimal batch size (capped to model's max_batch_size).
    """
    global _optimal_batch_size

    # Get model's max batch size limit
    max_batch = get_max_batch_size(model)

    # Use cached value if available (still respect max)
    if _optimal_batch_size is not None:
        return min(_optimal_batch_size, max_batch)

    # Check environment override (cap to model max)
    env_batch = os.environ.get(ENV_BATCH_SIZE)
    if env_batch:
        _optimal_batch_size = min(int(env_batch), max_batch)
        return _optimal_batch_size

    # Get appropriate default for this model type
    default_size = _get_default_batch_size(max_batch)

    # Need at least 8 samples for meaningful timing
    if len(sample_texts) < 8:
        _optimal_batch_size = default_size
        return _optimal_batch_size

    best_size = default_size
    best_rate = 0.0

    # Get batch sizes appropriate for this model
    valid_batch_sizes = _get_batch_sizes_for_model(max_batch)

    for batch_size in valid_batch_sizes:
        if batch_size > len(sample_texts):
            continue

        try:
            test_texts = sample_texts[:batch_size]
            start = time.perf_counter()
            _embed_batch(client, test_texts, model, dimensions)
            elapsed = time.perf_counter() - start

            rate = batch_size / elapsed  # texts per second
            if rate > best_rate:
                best_rate = rate
                best_size = batch_size
        except Exception:
            # If a batch size fails, skip it
            continue

    _optimal_batch_size = best_size
    return best_size


@overload
def embed_texts(
    texts: list[str],
    model: str | None = None,
    dimensions: int | None = None,
    *,
    return_timing: Literal[False] = False,
) -> tuple[list[bytes], int]:
    ...


@overload
def embed_texts(
    texts: list[str],
    model: str | None = None,
    dimensions: int | None = None,
    *,
    return_timing: Literal[True],
) -> tuple[list[bytes], int, float]:
    ...


def embed_texts(
    texts: list[str],
    model: str | None = None,
    dimensions: int | None = None,
    *,
    return_timing: bool = False,
) -> tuple[list[bytes], int] | tuple[list[bytes], int, float]:
    """
    Generate embeddings for a list of texts using OpenAI's API.

    Automatically batches large requests to prevent timeouts and improve
    throughput with local servers like LM Studio. Batch size is auto-tuned
    on first call or can be set via OGREP_BATCH_SIZE environment variable.

    Args:
        texts: List of text strings to embed.
        model: OpenAI embedding model name or alias.
            Defaults to OGREP_MODEL env var or "text-embedding-3-small".
            Accepts aliases: "small", "large", "ada".
        dimensions: Optional dimension override for models that support it.
            Defaults to OGREP_DIMENSIONS env var or model default.
        return_timing: If True, also returns the elapsed time in seconds.

    Returns:
        A tuple of (embeddings, dimension) or (embeddings, dimension, elapsed_s) where:
            - embeddings: List of float32 binary blobs (one per input text)
            - dimension: The embedding dimension (e.g., 1536 for small model)
            - elapsed_s: Time taken for API call in seconds (if return_timing=True)

    Raises:
        openai.OpenAIError: If the API call fails.
        ValueError: If model is not recognized.

    Example:
        >>> blobs, dim = embed_texts(["Hello world", "Goodbye"])
        >>> len(blobs)
        2
        >>> dim
        1536

        >>> # Using model alias
        >>> blobs, dim = embed_texts(["test"], model="large")
        >>> dim
        3072

        >>> # With timing
        >>> blobs, dim, elapsed = embed_texts(["test"], return_timing=True)
        >>> elapsed  # e.g., 0.234
    """
    if not texts:
        if return_timing:
            return [], 0, 0.0
        return [], 0

    start_time = time.perf_counter()

    # Resolve model and dimensions from args, env, or defaults
    resolved_model = resolve_model(model)
    resolved_dimensions = resolve_dimensions(dimensions, resolved_model)

    # Create client
    client, is_local = _create_client()

    # Check for explicit batch size override (supports serial mode with OGREP_BATCH_SIZE=1)
    env_batch = os.environ.get(ENV_BATCH_SIZE)
    if env_batch:
        batch_size = int(env_batch)
    elif len(texts) <= MIN_BATCH_THRESHOLD or not is_local:
        # For small batches or cloud API, send all at once
        vectors, dim = _embed_batch(client, texts, resolved_model, resolved_dimensions)
        if return_timing:
            return vectors, dim, time.perf_counter() - start_time
        return vectors, dim
    else:
        # For large batches with local server, use auto-tuned batching
        batch_size = _find_optimal_batch_size(
            client, texts, resolved_model, resolved_dimensions
        )

    all_vectors: list[bytes] = []
    dim: int | None = None

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors, batch_dim = _embed_batch(
            client, batch, resolved_model, resolved_dimensions
        )
        all_vectors.extend(vectors)
        if dim is None:
            dim = batch_dim

    assert dim is not None

    if return_timing:
        return all_vectors, dim, time.perf_counter() - start_time

    return all_vectors, dim
