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
"""

from __future__ import annotations

import array
import math
import os
import time
from typing import Literal, overload

from openai import OpenAI

from .models import resolve_dimensions, resolve_model


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


@overload
def embed_texts(
    texts: list[str],
    model: str | None = None,
    dimensions: int | None = None,
    *,
    return_timing: Literal[False] = False,
) -> tuple[list[bytes], int]: ...


@overload
def embed_texts(
    texts: list[str],
    model: str | None = None,
    dimensions: int | None = None,
    *,
    return_timing: Literal[True],
) -> tuple[list[bytes], int, float]: ...


def embed_texts(
    texts: list[str],
    model: str | None = None,
    dimensions: int | None = None,
    *,
    return_timing: bool = False,
) -> tuple[list[bytes], int] | tuple[list[bytes], int, float]:
    """
    Generate embeddings for a list of texts using OpenAI's API.

    Calls the OpenAI embeddings endpoint, normalizes the vectors,
    and converts them to compact float32 binary blobs for storage.

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
    start_time = time.perf_counter()

    # Resolve model and dimensions from args, env, or defaults
    resolved_model = resolve_model(model)
    resolved_dimensions = resolve_dimensions(dimensions, resolved_model)

    # Support local OpenAI-compatible servers (e.g., LM Studio)
    base_url = os.environ.get("OGREP_BASE_URL")
    if base_url:
        # Local servers don't require a real API key
        api_key = os.environ.get("OPENAI_API_KEY", "lm-studio")
        client = OpenAI(base_url=base_url, api_key=api_key)
    else:
        client = OpenAI()

    kwargs: dict = {"input": texts, "model": resolved_model}
    if resolved_dimensions is not None:
        kwargs["dimensions"] = resolved_dimensions

    resp = client.embeddings.create(**kwargs)

    vectors: list[bytes] = []
    dim: int | None = None
    for item in resp.data:
        v = _l2_normalize(list(item.embedding))
        if dim is None:
            dim = len(v)
        arr_f = array.array("f", v)  # float32
        vectors.append(arr_f.tobytes())

    assert dim is not None

    if return_timing:
        elapsed = time.perf_counter() - start_time
        return vectors, dim, elapsed

    return vectors, dim
