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

from .models import get_context_tokens, get_max_batch_size, resolve_dimensions, resolve_model

# Environment variable for batch size override
ENV_BATCH_SIZE = "OGREP_BATCH_SIZE"

# Default batch sizes for local models (small context windows)
LOCAL_BATCH_SIZES = [8, 16, 32, 64, 96]

# Minimum texts to trigger batching (below this, send all at once)
MIN_BATCH_THRESHOLD = 32

# Threshold to distinguish local vs cloud models
CLOUD_BATCH_THRESHOLD = 256

# Characters per token estimate for code
# OpenAI uses ~4 chars/token for English, but code with special chars,
# whitespace patterns, and non-ASCII can tokenize to fewer chars/token.
# Using 3 chars/token as baseline; auto-retry handles edge cases.
CHARS_PER_TOKEN = 3


def _estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text.

    Uses a conservative approximation of ~3 characters per token for code.
    This accounts for special characters, operators, and whitespace patterns
    that tokenize more densely than plain English text.

    Args:
        text: Text to estimate tokens for.

    Returns:
        Estimated number of tokens.
    """
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """
    Truncate text to fit within a token limit.

    Args:
        text: Text to truncate.
        max_tokens: Maximum number of tokens.

    Returns:
        Truncated text.
    """
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text
    # Truncate with some margin and add indicator
    truncated = text[: max_chars - 20] + "\n[...truncated...]"
    return truncated


def _create_token_aware_batches(
    texts: list[str],
    max_tokens: int,
    max_count: int | None = None,
) -> list[list[str]]:
    """
    Create batches of texts that respect token limits.

    Splits texts into batches where the total estimated tokens per batch
    doesn't exceed the model's context limit. Also handles single texts
    that exceed the limit by truncating them.

    Args:
        texts: List of texts to batch.
        max_tokens: Maximum tokens per batch (model's context limit).
        max_count: Optional maximum number of texts per batch.

    Returns:
        List of batches, where each batch is a list of texts.

    Warns:
        UserWarning: When a single text exceeds the context limit and is truncated.
    """
    import warnings

    if not texts:
        return []

    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens = 0

    # Leave some margin for safety (10%)
    effective_limit = int(max_tokens * 0.9)

    for text in texts:
        text_tokens = _estimate_tokens(text)

        # Handle oversized single text
        if text_tokens > effective_limit:
            # Flush current batch if any
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            # Truncate the text
            truncated = _truncate_to_tokens(text, effective_limit)
            warnings.warn(
                f"Text truncated from ~{text_tokens} tokens to ~{effective_limit} "
                f"tokens to fit context window ({len(text)} -> {len(truncated)} chars)",
                UserWarning,
                stacklevel=2,
            )
            batches.append([truncated])
            continue

        # Check if adding this text would exceed limits
        would_exceed_tokens = current_tokens + text_tokens > effective_limit
        would_exceed_count = max_count is not None and len(current_batch) >= max_count

        if current_batch and (would_exceed_tokens or would_exceed_count):
            # Start a new batch
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(text)
        current_tokens += text_tokens

    # Don't forget the last batch
    if current_batch:
        batches.append(current_batch)

    return batches


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
        next_size = int(start * (ratio**i))
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
    _retry_count: int = 0,
) -> tuple[list[bytes], int]:
    """
    Embed a single batch of texts.

    Automatically retries with truncated text if context limit is exceeded.

    Args:
        client: OpenAI client instance.
        texts: List of texts to embed.
        model: Resolved model name.
        dimensions: Optional dimension override.
        _retry_count: Internal retry counter.

    Returns:
        Tuple of (embeddings, dimension).
    """
    import re
    import warnings

    from openai import BadRequestError

    kwargs: dict = {"input": texts, "model": model}
    if dimensions is not None:
        kwargs["dimensions"] = dimensions

    try:
        resp = client.embeddings.create(**kwargs)
    except BadRequestError as e:
        error_msg = str(e)
        # Check if it's a context length error
        if "maximum context length" in error_msg and _retry_count < 3:
            # Parse the error to find how much to reduce
            # Example: "maximum context length is 8192 tokens, however you requested 9047 tokens"
            match = re.search(
                r"maximum context length is (\d+) tokens.*requested (\d+) tokens", error_msg
            )
            if match:
                max_allowed = int(match.group(1))
                requested = int(match.group(2))
                # Calculate reduction ratio with extra margin
                ratio = (max_allowed * 0.85) / requested

                warnings.warn(
                    f"Context overflow ({requested} > {max_allowed} tokens). "
                    f"Truncating to {ratio:.0%} and retrying...",
                    UserWarning,
                    stacklevel=3,
                )

                # Truncate all texts by the ratio
                truncated_texts = []
                for text in texts:
                    new_len = int(len(text) * ratio)
                    if new_len < len(text):
                        truncated_texts.append(text[:new_len] + "\n[...truncated...]")
                    else:
                        truncated_texts.append(text)

                # Retry with truncated texts
                return _embed_batch(client, truncated_texts, model, dimensions, _retry_count + 1)
        raise

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

    # Get model limits
    max_tokens = get_context_tokens(resolved_model)
    max_batch = get_max_batch_size(resolved_model)

    # Determine count-based batch size
    env_batch = os.environ.get(ENV_BATCH_SIZE)
    if env_batch:
        batch_count = int(env_batch)
    elif len(texts) <= MIN_BATCH_THRESHOLD and not is_local:
        # For small cloud batches, use all texts (still subject to token limit)
        batch_count = len(texts)
    elif is_local:
        # For local server, use auto-tuned batching
        batch_count = _find_optimal_batch_size(client, texts, resolved_model, resolved_dimensions)
    else:
        # For cloud API with many texts, use model's max batch
        batch_count = max_batch

    # Create token-aware batches (respects both token limit and count limit)
    batches = _create_token_aware_batches(texts, max_tokens=max_tokens, max_count=batch_count)

    all_vectors: list[bytes] = []
    dim: int | None = None

    for batch in batches:
        vectors, batch_dim = _embed_batch(client, batch, resolved_model, resolved_dimensions)
        all_vectors.extend(vectors)
        if dim is None:
            dim = batch_dim

    assert dim is not None

    if return_timing:
        return all_vectors, dim, time.perf_counter() - start_time

    return all_vectors, dim
