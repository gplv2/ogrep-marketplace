"""
Embedding model definitions for ogrep.

Defines available OpenAI embedding models with their characteristics,
pricing, and recommended use cases. Supports configuration via
environment variable OGREP_MODEL.

Environment Variables:
    OGREP_MODEL: Default embedding model to use (e.g., "text-embedding-3-small")
    OGREP_DIMENSIONS: Default embedding dimensions (optional, model-specific)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Environment variable names
ENV_MODEL = "OGREP_MODEL"
ENV_DIMENSIONS = "OGREP_DIMENSIONS"
ENV_CHUNK_LINES = "OGREP_CHUNK_LINES"
ENV_OVERLAP_LINES = "OGREP_OVERLAP_LINES"
ENV_BASE_URL = "OGREP_BASE_URL"

# Default models
DEFAULT_OPENAI_MODEL = "text-embedding-3-small"
DEFAULT_LOCAL_MODEL = "nomic-embed-text-v1.5"  # nomic - best balance of accuracy and speed


def _get_default_model() -> str:
    """
    Get the default model based on environment configuration.

    If OGREP_BASE_URL is set (local server), defaults to nomic.
    Otherwise, defaults to OpenAI's text-embedding-3-small.

    Returns:
        Default model ID.
    """
    if os.environ.get(ENV_BASE_URL):
        return DEFAULT_LOCAL_MODEL
    return DEFAULT_OPENAI_MODEL


# Legacy alias for backwards compatibility
DEFAULT_MODEL = DEFAULT_OPENAI_MODEL

# Default chunk size and overlap for models without specific tuning
# These are starting points - run `ogrep tune` on your codebase for best results
DEFAULT_CHUNK_LINES = 60
DEFAULT_OVERLAP_LINES = 10


# Default max batch size for models without specific tuning
DEFAULT_MAX_BATCH_SIZE = 16


@dataclass(frozen=True)
class EmbeddingModel:
    """
    Definition of an OpenAI embedding model.

    Attributes:
        id: Model identifier used in API calls.
        name: Human-readable model name.
        description: Brief description of capabilities.
        dimensions: Default output dimensions.
        max_dimensions: Maximum supported dimensions (for flexible models).
        price_per_million: Cost per million tokens in USD.
        use_cases: Recommended use cases for this model.
        notes: Additional notes or caveats.
        optimal_chunk_lines: Tuned chunk size for best accuracy (model-specific).
        optimal_overlap_lines: Tuned overlap between chunks (model-specific).
        context_tokens: Model's context window size in tokens.
        max_batch_size: Maximum batch size for embedding requests.
    """

    id: str
    name: str
    description: str
    dimensions: int
    max_dimensions: int | None
    price_per_million: float
    use_cases: tuple[str, ...]
    notes: str | None = None
    optimal_chunk_lines: int = DEFAULT_CHUNK_LINES
    optimal_overlap_lines: int = DEFAULT_OVERLAP_LINES
    context_tokens: int = 8192  # Default context window
    max_batch_size: int = DEFAULT_MAX_BATCH_SIZE


# Available OpenAI embedding models
# Source: https://platform.openai.com/docs/models
MODELS: dict[str, EmbeddingModel] = {
    "text-embedding-3-small": EmbeddingModel(
        id="text-embedding-3-small",
        name="Text Embedding 3 Small",
        description="Fast, affordable embeddings for most use cases",
        dimensions=1536,
        max_dimensions=1536,
        price_per_million=0.02,
        use_cases=(
            "Semantic search",
            "Code search",
            "Clustering",
            "Classification",
            "RAG applications",
        ),
        notes="Best balance of cost and performance. Recommended for most projects.",
        context_tokens=8191,
        max_batch_size=2048,  # OpenAI API limit
    ),
    "text-embedding-3-large": EmbeddingModel(
        id="text-embedding-3-large",
        name="Text Embedding 3 Large",
        description="Most capable model for complex semantic tasks",
        dimensions=3072,
        max_dimensions=3072,
        price_per_million=0.13,
        use_cases=(
            "High-accuracy semantic search",
            "Multi-language support",
            "Complex code understanding",
            "Fine-grained similarity",
            "Production RAG systems",
        ),
        notes="54.9% avg on MIRACL (vs 31.4% for ada-002). Supports dimension reduction.",
        context_tokens=8191,
        max_batch_size=2048,  # OpenAI API limit
    ),
    "text-embedding-ada-002": EmbeddingModel(
        id="text-embedding-ada-002",
        name="Text Embedding Ada 002",
        description="Legacy model, still widely used",
        dimensions=1536,
        max_dimensions=None,  # Does not support dimension reduction
        price_per_million=0.10,
        use_cases=(
            "Legacy compatibility",
            "Existing indexes",
        ),
        notes="Legacy model. Consider migrating to text-embedding-3-small for better performance.",
        context_tokens=8191,
        max_batch_size=2048,  # OpenAI API limit
    ),
    # Local models via LM Studio
    # Optimal chunk sizes determined by tuning on real codebases
    # Max batch sizes set conservatively based on context windows
    "bge-base-en-v1.5": EmbeddingModel(
        id="bge-base-en-v1.5",
        name="BGE Base English v1.5 (Local)",
        description="Local embedding model via LM Studio (768D)",
        dimensions=768,
        max_dimensions=None,
        price_per_million=0.0,
        use_cases=(
            "Local/offline search",
            "Privacy-sensitive",
            "Cost-free",
        ),
        notes="Requires: lms server start. Set OGREP_BASE_URL=http://localhost:1234/v1",
        optimal_chunk_lines=30,  # Tuned: performs best with smaller chunks
        optimal_overlap_lines=5,  # Tuned: BGE prefers minimal overlap
        context_tokens=512,
        max_batch_size=16,  # Conservative for small context
    ),
    "nomic-embed-text-v1.5": EmbeddingModel(
        id="nomic-embed-text-v1.5",
        name="Nomic Embed Text v1.5 (Local)",
        description="Local embedding model via LM Studio (768D, 8192 token context)",
        dimensions=768,
        max_dimensions=None,
        price_per_million=0.0,
        use_cases=(
            "Local/offline search",
            "Privacy-sensitive",
            "Cost-free",
        ),
        notes="Large context window (8192 tokens). Run: lms load nomic-ai/nomic-embed-text-v1.5",
        optimal_chunk_lines=30,  # Tuned: benchmark shows 30 lines optimal
        optimal_overlap_lines=15,  # Tuned: nomic benefits from more overlap
        context_tokens=8192,
        max_batch_size=32,  # Larger context allows bigger batches
    ),
    "text-embedding-all-minilm-l6-v2-embedding": EmbeddingModel(
        id="text-embedding-all-minilm-l6-v2-embedding",
        name="MiniLM L6 v2 (Local)",
        description="Fast, lightweight local embedding model (384D, 256 token limit)",
        dimensions=384,
        max_dimensions=None,
        price_per_million=0.0,
        use_cases=(
            "Local/offline search",
            "Fast inference",
            "Low memory usage",
        ),
        notes="Smallest model (~25MB) but truncates >256 tokens. Run: lms load all-minilm-l6-v2",
        optimal_chunk_lines=30,  # Tuned: small chunks fit context window
        optimal_overlap_lines=15,  # Tuned: more overlap helps with small context
        context_tokens=256,
        max_batch_size=16,  # Small model but fast, keep batches moderate
    ),
    "text-embedding-bge-m3": EmbeddingModel(
        id="text-embedding-bge-m3",
        name="BGE-M3 (Local)",
        description="Multi-lingual, multi-functionality embedding model (1024D)",
        dimensions=1024,
        max_dimensions=None,
        price_per_million=0.0,
        use_cases=(
            "Multi-lingual code search",
            "Dense + sparse retrieval",
            "100+ languages",
        ),
        notes="Supports dense, multi-vector, and sparse retrieval. Run: lms load bge-m3",
        optimal_chunk_lines=60,
        optimal_overlap_lines=10,  # Tuned: moderate overlap for larger chunks
        context_tokens=8192,
        max_batch_size=32,  # Large context allows bigger batches
    ),
}

# Model aliases for convenience
MODEL_ALIASES: dict[str, str] = {
    "small": "text-embedding-3-small",
    "large": "text-embedding-3-large",
    "ada": "text-embedding-ada-002",
    "3-small": "text-embedding-3-small",
    "3-large": "text-embedding-3-large",
    # Local model aliases
    "bge": "bge-base-en-v1.5",
    "bge-m3": "text-embedding-bge-m3",
    "nomic": "nomic-embed-text-v1.5",
    "minilm": "text-embedding-all-minilm-l6-v2-embedding",
    "local": "nomic-embed-text-v1.5",  # Default local model
}


def resolve_model(model: str | None = None) -> str:
    """
    Resolve model identifier from input, alias, or environment.

    Priority:
        1. Explicit model argument
        2. OGREP_MODEL environment variable
        3. Smart default based on environment:
           - If OGREP_BASE_URL is set: nomic (local model)
           - Otherwise: text-embedding-3-small (OpenAI)

    Args:
        model: Model ID, alias, or None to use default/env.

    Returns:
        Resolved model identifier.

    Raises:
        ValueError: If model is not recognized.

    Examples:
        >>> resolve_model("small")
        'text-embedding-3-small'
        >>> resolve_model("text-embedding-3-large")
        'text-embedding-3-large'
        >>> resolve_model(None)  # Uses env or smart default
        'text-embedding-3-small'  # or 'nomic' if OGREP_BASE_URL is set
    """
    # Use explicit argument, env var, or smart default
    model_input = model or os.environ.get(ENV_MODEL) or _get_default_model()

    # Resolve alias if applicable
    resolved = MODEL_ALIASES.get(model_input, model_input)

    # Validate model exists
    if resolved not in MODELS:
        valid = ", ".join(sorted(MODELS.keys()))
        aliases = ", ".join(sorted(MODEL_ALIASES.keys()))
        raise ValueError(
            f"Unknown model: {model_input!r}. Valid models: {valid}. Aliases: {aliases}."
        )

    return resolved


def resolve_dimensions(dimensions: int | None = None, model: str | None = None) -> int | None:
    """
    Resolve embedding dimensions from input or environment.

    Args:
        dimensions: Explicit dimensions or None.
        model: Model ID to get default dimensions from.

    Returns:
        Resolved dimensions or None for model default.
    """
    if dimensions is not None:
        return dimensions

    env_dim = os.environ.get(ENV_DIMENSIONS)
    if env_dim:
        return int(env_dim)

    return None


def get_model(model_id: str) -> EmbeddingModel:
    """
    Get model definition by ID.

    Args:
        model_id: Model identifier.

    Returns:
        EmbeddingModel instance.

    Raises:
        KeyError: If model not found.
    """
    return MODELS[model_id]


def list_models() -> list[EmbeddingModel]:
    """
    List all available embedding models.

    Returns:
        List of EmbeddingModel instances, sorted by price.
    """
    return sorted(MODELS.values(), key=lambda m: m.price_per_million)


def get_optimal_chunk_lines(model: str | None = None) -> int:
    """
    Get the optimal chunk size for a model.

    Priority:
        1. OGREP_CHUNK_LINES environment variable (user's tuned value)
        2. Model-specific default from tuning tests
        3. Global default (60 lines)

    The model-specific defaults are starting points based on initial testing.
    Different codebases may have very different optimal settings - use
    `ogrep tune` to find the best chunk size for your specific repository.

    Args:
        model: Model ID, alias, or None to use default/env.

    Returns:
        Chunk size in lines.

    Examples:
        >>> # With OGREP_CHUNK_LINES=45 set in environment
        >>> get_optimal_chunk_lines("nomic")
        45

        >>> # Without env var, uses model default
        >>> get_optimal_chunk_lines("nomic")
        30
        >>> get_optimal_chunk_lines("bge")
        30
        >>> get_optimal_chunk_lines("small")
        60
    """
    # User's tuned value takes precedence
    env_chunk = os.environ.get(ENV_CHUNK_LINES)
    if env_chunk:
        return int(env_chunk)

    # Fall back to model-specific default
    resolved = resolve_model(model)
    return MODELS[resolved].optimal_chunk_lines


def get_optimal_overlap(model: str | None = None) -> int:
    """
    Get the optimal overlap size for a model.

    Priority:
        1. OGREP_OVERLAP_LINES environment variable (user's tuned value)
        2. Model-specific default from tuning tests
        3. Global default (10 lines)

    The model-specific defaults are based on benchmarking results. Different
    models perform best with different overlap sizes:
        - nomic/minilm: 15 lines (benefits from more context)
        - bge: 5 lines (prefers minimal overlap)
        - OpenAI/bge-m3: 10 lines (moderate overlap)

    Args:
        model: Model ID, alias, or None to use default/env.

    Returns:
        Overlap size in lines.

    Examples:
        >>> # With OGREP_OVERLAP_LINES=15 set in environment
        >>> get_optimal_overlap("bge")
        15

        >>> # Without env var, uses model default
        >>> get_optimal_overlap("nomic")
        15
        >>> get_optimal_overlap("bge")
        5
        >>> get_optimal_overlap("small")
        10
    """
    # User's tuned value takes precedence
    env_overlap = os.environ.get(ENV_OVERLAP_LINES)
    if env_overlap:
        return int(env_overlap)

    # Fall back to model-specific default
    resolved = resolve_model(model)
    return MODELS[resolved].optimal_overlap_lines


def get_max_batch_size(model: str | None = None) -> int:
    """
    Get the maximum batch size for a model.

    Returns the model's max_batch_size to prevent exceeding context limits
    or causing memory issues with local embedding servers.

    Args:
        model: Model ID, alias, or None to use default/env.

    Returns:
        Maximum batch size for embedding requests.

    Examples:
        >>> get_max_batch_size("minilm")
        16
        >>> get_max_batch_size("nomic")
        32
        >>> get_max_batch_size("small")
        2048
    """
    resolved = resolve_model(model)
    return MODELS[resolved].max_batch_size


def get_context_tokens(model: str | None = None) -> int:
    """
    Get the context window size for a model in tokens.

    Args:
        model: Model ID, alias, or None to use default/env.

    Returns:
        Context window size in tokens.

    Examples:
        >>> get_context_tokens("minilm")
        256
        >>> get_context_tokens("nomic")
        8192
    """
    resolved = resolve_model(model)
    return MODELS[resolved].context_tokens


def format_models_table() -> str:
    """
    Format models as a human-readable table.

    Returns:
        Formatted string with model comparison table.
    """
    lines = [
        "Available OpenAI Embedding Models",
        "=" * 60,
        "",
    ]

    for model in list_models():
        lines.extend(
            [
                f"{model.name} ({model.id})",
                "-" * 60,
                f"  {model.description}",
                f"  Dimensions: {model.dimensions}"
                + (f" (max: {model.max_dimensions})" if model.max_dimensions else ""),
                f"  Price: ${model.price_per_million:.2f} / million tokens",
                f"  Use cases: {', '.join(model.use_cases)}",
            ]
        )
        if model.notes:
            lines.append(f"  Note: {model.notes}")
        lines.append("")

    lines.extend(
        [
            "Configuration:",
            f"  Set {ENV_MODEL} environment variable to change default model",
            f"  Set {ENV_DIMENSIONS} environment variable to change default dimensions",
            "",
            "Aliases:",
            "  small  -> text-embedding-3-small",
            "  large  -> text-embedding-3-large",
            "  ada    -> text-embedding-ada-002",
            "  bge    -> bge-base-en-v1.5 (local)",
            "  bge-m3 -> text-embedding-bge-m3 (local)",
            "  nomic  -> nomic-embed-text-v1.5 (local)",
            "  minilm -> all-minilm-l6-v2 (local)",
            "  local  -> nomic-embed-text-v1.5",
            "",
            "Local Models (via LM Studio):",
            "=" * 60,
            "",
            "Install:",
            "  1. Download LM Studio from https://lmstudio.ai/",
            "  2. Run: ~/.lmstudio/bin/lms bootstrap",
            "",
            "Setup:",
            "  1. lms load nomic-ai/nomic-embed-text-v1.5 -y",
            "  2. lms server start",
            "  3. export OGREP_BASE_URL=http://localhost:1234/v1",
            "",
            "Usage:",
            "  ogrep index . -m nomic",
            "  ogrep query 'search term' -m nomic",
        ]
    )

    return "\n".join(lines)
