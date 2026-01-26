"""
Embedding module for ogrep.

Provides text embedding functionality using OpenAI's embedding API,
Voyage AI's API, or a local OpenAI-compatible server (like LM Studio).

Embeddings are L2-normalized for cosine similarity calculations and
stored as compact float32 binary blobs.

Requires:
    OPENAI_API_KEY environment variable (not required for local servers).
    VOYAGE_API_KEY environment variable (for Voyage AI models).

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

# Voyage AI environment variables
ENV_VOYAGE_API_KEY = "VOYAGE_API_KEY"
ENV_VOYAGE_TIMEOUT = "OGREP_VOYAGE_TIMEOUT"  # Timeout in seconds (default: 120)
ENV_VOYAGE_RETRIES = "OGREP_VOYAGE_RETRIES"  # Max retries (default: 2)
ENV_VOYAGE_CHARS_PER_TOKEN = "OGREP_VOYAGE_CHARS_PER_TOKEN"  # Token estimation ratio (default: 1.0)

# Voyage defaults
DEFAULT_VOYAGE_TIMEOUT = 120.0  # 2 minutes
DEFAULT_VOYAGE_RETRIES = 2
DEFAULT_VOYAGE_CHARS_PER_TOKEN = 1.0  # Conservative: assume 1 char = 1 token for code


def _is_voyage_model(model: str) -> bool:
    """
    Check if model requires Voyage AI backend.

    Args:
        model: Model ID or alias.

    Returns:
        True if this is a Voyage AI model.
    """
    return model.startswith("voyage-") or model in ("voyage", "voyage-code", "voyage-lite")


def _embed_voyage(
    texts: list[str],
    model: str,
    input_type: str = "document",
) -> tuple[list[bytes], int]:
    """
    Embed texts using Voyage AI API.

    Args:
        texts: List of texts to embed.
        model: Voyage AI model name (e.g., "voyage-code-3").
        input_type: Type of input for better retrieval ("document" or "query").

    Returns:
        Tuple of (embedding_blobs, dimension).

    Raises:
        ImportError: If voyageai package is not installed.
        ValueError: If VOYAGE_API_KEY is not set.
    """
    try:
        import voyageai
    except ImportError as e:
        raise ImportError(
            "Voyage AI embeddings require the voyageai package. "
            "Install with: pip install 'ogrep[voyage]'"
        ) from e

    api_key = os.environ.get(ENV_VOYAGE_API_KEY)
    if not api_key:
        raise ValueError(
            f"{ENV_VOYAGE_API_KEY} environment variable is not set. "
            "Get an API key from https://www.voyageai.com/"
        )

    # Get timeout and retry settings
    timeout_str = os.environ.get(ENV_VOYAGE_TIMEOUT)
    timeout = float(timeout_str) if timeout_str else DEFAULT_VOYAGE_TIMEOUT
    retries_str = os.environ.get(ENV_VOYAGE_RETRIES)
    max_retries = int(retries_str) if retries_str else DEFAULT_VOYAGE_RETRIES

    client = voyageai.Client(
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries,
    )

    # Voyage API call with timing for slow request detection
    start_time = time.time()
    try:
        result = client.embed(
            texts=texts,
            model=model,
            input_type=input_type,
        )
    except Exception as e:
        error_msg = str(e)
        # Handle batch token limit errors gracefully
        if "tokens" in error_msg.lower() and "batch" in error_msg.lower():
            raise RuntimeError(
                f"Voyage API batch token limit exceeded ({len(texts)} texts in batch). "
                f"This is an internal error - please report it at "
                f"https://github.com/gplv2/ogrep/issues\n"
                f"Original error: {error_msg}"
            ) from None
        # Handle rate limiting
        if "rate" in error_msg.lower() or "429" in error_msg:
            raise RuntimeError(
                f"Voyage API rate limit reached. Wait a moment and try again.\n"
                f"Original error: {error_msg}"
            ) from None
        # Handle authentication errors
        if "auth" in error_msg.lower() or "api key" in error_msg.lower() or "401" in error_msg:
            raise RuntimeError(
                f"Voyage API authentication failed. Check your VOYAGE_API_KEY.\n"
                f"Original error: {error_msg}"
            ) from None
        # Handle connection errors
        if any(
            term in error_msg.lower() for term in ["connect", "timeout", "network", "unreachable"]
        ):
            raise RuntimeError(
                f"Could not connect to Voyage API. Check your network connection.\n"
                f"Original error: {error_msg}"
            ) from None
        # Re-raise other errors with context
        raise RuntimeError(f"Voyage API error: {error_msg}") from None
    elapsed = time.time() - start_time

    # Warn on slow requests (>30s per batch is unusual)
    if elapsed > 30:
        import sys

        print(
            f"Warning: Voyage API request took {elapsed:.1f}s for {len(texts)} texts",
            file=sys.stderr,
        )

    # Convert to normalized float32 blobs
    blobs = []
    for emb in result.embeddings:
        normalized = _l2_normalize(emb)
        blob = array.array("f", normalized).tobytes()
        blobs.append(blob)

    dim = len(result.embeddings[0]) if result.embeddings else 0
    return blobs, dim


# Voyage AI batch token limit (per API request)
# The API returns: "max allowed tokens per submitted batch is 120000"
VOYAGE_BATCH_TOKEN_LIMIT = 120000


def _get_voyage_chars_per_token() -> float:
    """
    Get the chars-per-token ratio for Voyage token estimation.

    Configurable via OGREP_VOYAGE_CHARS_PER_TOKEN environment variable.
    Default is 1.0 (conservative: assume 1 char = 1 token for code).

    Returns:
        Chars per token ratio.
    """
    env_val = os.environ.get(ENV_VOYAGE_CHARS_PER_TOKEN)
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass
    return DEFAULT_VOYAGE_CHARS_PER_TOKEN


def _estimate_voyage_tokens(text: str) -> int:
    """
    Estimate tokens for Voyage AI's tokenizer.

    Voyage uses a more aggressive tokenizer than OpenAI, especially for code.
    The estimation ratio is configurable via OGREP_VOYAGE_CHARS_PER_TOKEN.

    Args:
        text: Text to estimate tokens for.

    Returns:
        Estimated number of tokens.
    """
    if not text:
        return 0
    chars_per_token = _get_voyage_chars_per_token()
    return max(1, int(len(text) / chars_per_token))


def _create_voyage_batches(
    texts: list[str],
    max_tokens: int,
    max_count: int | None = None,
) -> list[list[str]]:
    """
    Create batches of texts for Voyage AI that respect token limits.

    Uses Voyage-specific token estimation which is more conservative
    than the standard estimate.

    Args:
        texts: List of texts to batch.
        max_tokens: Maximum tokens per batch.
        max_count: Optional maximum texts per batch.

    Returns:
        List of text batches.
    """
    if not texts:
        return []

    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens = 0

    for text in texts:
        text_tokens = _estimate_voyage_tokens(text)

        # If single text exceeds limit, truncate it
        if text_tokens > max_tokens:
            # Truncate to fit
            chars_per_token = _get_voyage_chars_per_token()
            max_chars = int(max_tokens * chars_per_token * 0.9)  # 90% margin
            text = text[:max_chars] + "\n[...truncated...]"
            text_tokens = _estimate_voyage_tokens(text)

        # Check if adding this text would exceed limits
        would_exceed_tokens = (current_tokens + text_tokens) > max_tokens
        would_exceed_count = max_count is not None and len(current_batch) >= max_count

        if current_batch and (would_exceed_tokens or would_exceed_count):
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(text)
        current_tokens += text_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def _embed_voyage_batched(
    texts: list[str],
    model: str,
    input_type: str = "document",
    max_batch_count: int = 128,
) -> tuple[list[bytes], int]:
    """
    Embed texts using Voyage AI API with token-aware batching.

    Voyage API has a limit of 120,000 tokens per batch request.
    This function creates batches that respect both token and count limits,
    using Voyage-specific token estimation.

    Args:
        texts: List of texts to embed.
        model: Voyage AI model name.
        input_type: Type of input ("document" or "query").
        max_batch_count: Maximum texts per API call.

    Returns:
        Tuple of (embedding_blobs, dimension).
    """
    if not texts:
        return [], 0

    # Use Voyage-specific batching with conservative token estimation
    # Apply 80% safety margin due to tokenizer estimation variance
    max_tokens = int(VOYAGE_BATCH_TOKEN_LIMIT * 0.8)
    batches = _create_voyage_batches(texts, max_tokens=max_tokens, max_count=max_batch_count)

    all_blobs: list[bytes] = []
    dim: int = 0

    # Process each token-aware batch
    for batch in batches:
        blobs, batch_dim = _embed_voyage(batch, model, input_type)
        all_blobs.extend(blobs)
        if dim == 0:
            dim = batch_dim

    return all_blobs, dim


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

    from openai import APIConnectionError, AuthenticationError, BadRequestError, RateLimitError

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
        # Other bad request errors
        base_url = os.environ.get("OGREP_BASE_URL")
        api_name = f"Local embedding server ({base_url})" if base_url else "OpenAI API"
        raise RuntimeError(
            f"{api_name} request failed: {error_msg}\n"
            f"Model: {model}, Batch size: {len(texts)} texts"
        ) from None
    except RateLimitError as e:
        base_url = os.environ.get("OGREP_BASE_URL")
        if base_url:
            raise RuntimeError(
                f"Local embedding server rate limit reached. Wait a moment and try again.\n"
                f"Server: {base_url}\n"
                f"Original error: {e}"
            ) from None
        raise RuntimeError(
            f"OpenAI API rate limit reached. Wait a moment and try again.\nOriginal error: {e}"
        ) from None
    except AuthenticationError as e:
        base_url = os.environ.get("OGREP_BASE_URL")
        if base_url:
            raise RuntimeError(
                f"Local embedding server authentication failed.\n"
                f"Server: {base_url}\n"
                f"Original error: {e}"
            ) from None
        raise RuntimeError(
            f"OpenAI API authentication failed. Check your OPENAI_API_KEY.\nOriginal error: {e}"
        ) from None
    except APIConnectionError as e:
        base_url = os.environ.get("OGREP_BASE_URL")
        if base_url:
            raise RuntimeError(
                f"Could not connect to local embedding server at {base_url}.\n"
                f"Check that the server is running and the URL is correct.\n"
                f"Original error: {e}"
            ) from None
        raise RuntimeError(
            f"Could not connect to OpenAI API. Check your network connection.\nOriginal error: {e}"
        ) from None
    except Exception as e:
        base_url = os.environ.get("OGREP_BASE_URL")
        api_name = f"Local embedding server ({base_url})" if base_url else "OpenAI API"
        raise RuntimeError(f"{api_name} error: {e}") from None

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

    # Route to Voyage AI backend if applicable
    if _is_voyage_model(resolved_model):
        blobs, dim = _embed_voyage_batched(texts, resolved_model, input_type="document")
        if return_timing:
            return blobs, dim, time.perf_counter() - start_time
        return blobs, dim

    # Create OpenAI client for OpenAI/local models
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
