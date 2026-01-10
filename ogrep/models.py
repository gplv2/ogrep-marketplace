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

# Default model if not specified
DEFAULT_MODEL = "text-embedding-3-small"


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
    """

    id: str
    name: str
    description: str
    dimensions: int
    max_dimensions: int | None
    price_per_million: float
    use_cases: tuple[str, ...]
    notes: str | None = None


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
    ),
}

# Model aliases for convenience
MODEL_ALIASES: dict[str, str] = {
    "small": "text-embedding-3-small",
    "large": "text-embedding-3-large",
    "ada": "text-embedding-ada-002",
    "3-small": "text-embedding-3-small",
    "3-large": "text-embedding-3-large",
}


def resolve_model(model: str | None = None) -> str:
    """
    Resolve model identifier from input, alias, or environment.

    Priority:
        1. Explicit model argument
        2. OGREP_MODEL environment variable
        3. Default model (text-embedding-3-small)

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
        >>> resolve_model(None)  # Uses env or default
        'text-embedding-3-small'
    """
    # Use explicit argument, env var, or default
    model_input = model or os.environ.get(ENV_MODEL) or DEFAULT_MODEL

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
            "  small -> text-embedding-3-small",
            "  large -> text-embedding-3-large",
            "  ada   -> text-embedding-ada-002",
        ]
    )

    return "\n".join(lines)
