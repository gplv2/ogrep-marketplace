"""
Embedding module for ogrep.

Provides text embedding functionality using OpenAI's embedding API.
Embeddings are L2-normalized for cosine similarity calculations and
stored as compact float32 binary blobs.

Requires:
    OPENAI_API_KEY environment variable to be set.
"""

from __future__ import annotations

import array
import math

from openai import OpenAI


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


def embed_texts(
    texts: list[str],
    model: str = "text-embedding-3-small",
    dimensions: int | None = None,
) -> tuple[list[bytes], int]:
    """
    Generate embeddings for a list of texts using OpenAI's API.

    Calls the OpenAI embeddings endpoint, normalizes the vectors,
    and converts them to compact float32 binary blobs for storage.

    Args:
        texts: List of text strings to embed.
        model: OpenAI embedding model name.
            Default is "text-embedding-3-small" which offers a good
            balance of quality and cost.
        dimensions: Optional dimension override for models that support it.
            If None, uses the model's default dimensions.

    Returns:
        A tuple of (embeddings, dimension) where:
            - embeddings: List of float32 binary blobs (one per input text)
            - dimension: The embedding dimension (e.g., 1536 for ada-002)

    Raises:
        openai.OpenAIError: If the API call fails.

    Example:
        >>> blobs, dim = embed_texts(["Hello world", "Goodbye"])
        >>> len(blobs)
        2
        >>> dim
        1536
    """
    client = OpenAI()

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
        arr_f = array.array("f", v)  # float32
        vectors.append(arr_f.tobytes())

    assert dim is not None
    return vectors, dim
