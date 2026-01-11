"""Tests for ogrep.models module."""

from __future__ import annotations

import pytest

from ogrep.models import (
    DEFAULT_CHUNK_LINES,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OVERLAP_LINES,
    MODEL_ALIASES,
    MODELS,
    EmbeddingModel,
    _get_default_model,
    format_models_table,
    get_model,
    get_optimal_chunk_lines,
    get_optimal_overlap,
    list_models,
    resolve_dimensions,
    resolve_model,
)


class TestResolveModel:
    """Tests for resolve_model function."""

    def test_resolve_explicit_model_id(self) -> None:
        """Test resolving an explicit model ID."""
        assert resolve_model("text-embedding-3-small") == "text-embedding-3-small"
        assert resolve_model("text-embedding-3-large") == "text-embedding-3-large"
        assert resolve_model("text-embedding-ada-002") == "text-embedding-ada-002"

    def test_resolve_model_alias(self) -> None:
        """Test resolving model aliases."""
        assert resolve_model("small") == "text-embedding-3-small"
        assert resolve_model("large") == "text-embedding-3-large"
        assert resolve_model("ada") == "text-embedding-ada-002"

    def test_resolve_local_model_aliases(self) -> None:
        """Test resolving local model aliases."""
        assert resolve_model("bge") == "bge-base-en-v1.5"
        assert resolve_model("nomic") == "nomic-embed-text-v1.5"
        assert resolve_model("minilm") == "text-embedding-all-minilm-l6-v2-embedding"
        assert resolve_model("local") == "nomic-embed-text-v1.5"

    def test_resolve_model_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolving model from environment variable."""
        monkeypatch.setenv("OGREP_MODEL", "large")
        assert resolve_model(None) == "text-embedding-3-large"

    def test_resolve_model_explicit_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that explicit model overrides environment variable."""
        monkeypatch.setenv("OGREP_MODEL", "large")
        assert resolve_model("small") == "text-embedding-3-small"

    def test_resolve_model_default_openai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default model is OpenAI when no local server configured."""
        monkeypatch.delenv("OGREP_MODEL", raising=False)
        monkeypatch.delenv("OGREP_BASE_URL", raising=False)
        assert resolve_model(None) == DEFAULT_OPENAI_MODEL

    def test_resolve_model_default_local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default model is local (nomic) when OGREP_BASE_URL is set."""
        monkeypatch.delenv("OGREP_MODEL", raising=False)
        monkeypatch.setenv("OGREP_BASE_URL", "http://localhost:1234/v1")
        assert resolve_model(None) == DEFAULT_LOCAL_MODEL

    def test_resolve_model_local_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test local server takes precedence even with OPENAI_API_KEY set."""
        monkeypatch.delenv("OGREP_MODEL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("OGREP_BASE_URL", "http://localhost:1234/v1")
        assert resolve_model(None) == DEFAULT_LOCAL_MODEL

    def test_resolve_model_invalid_raises(self) -> None:
        """Test that invalid model raises ValueError."""
        with pytest.raises(ValueError, match="Unknown model"):
            resolve_model("invalid-model")

    def test_resolve_model_error_message_includes_valid_options(self) -> None:
        """Test that error message includes valid models and aliases."""
        with pytest.raises(ValueError) as exc_info:
            resolve_model("nonexistent")
        error_msg = str(exc_info.value)
        assert "text-embedding-3-small" in error_msg
        assert "small" in error_msg


class TestGetDefaultModel:
    """Tests for _get_default_model function."""

    def test_default_openai_when_no_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns OpenAI model when OGREP_BASE_URL is not set."""
        monkeypatch.delenv("OGREP_BASE_URL", raising=False)
        assert _get_default_model() == DEFAULT_OPENAI_MODEL

    def test_default_local_when_base_url_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns local model when OGREP_BASE_URL is set."""
        monkeypatch.setenv("OGREP_BASE_URL", "http://localhost:1234/v1")
        assert _get_default_model() == DEFAULT_LOCAL_MODEL

    def test_default_local_model_is_nomic(self) -> None:
        """Test that the default local model is nomic."""
        assert DEFAULT_LOCAL_MODEL == "nomic-embed-text-v1.5"
        assert MODEL_ALIASES["nomic"] == DEFAULT_LOCAL_MODEL


class TestResolveDimensions:
    """Tests for resolve_dimensions function."""

    def test_explicit_dimensions_returned(self) -> None:
        """Test that explicit dimensions are returned."""
        assert resolve_dimensions(512) == 512
        assert resolve_dimensions(1024, model="small") == 1024

    def test_dimensions_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test reading dimensions from environment variable."""
        monkeypatch.setenv("OGREP_DIMENSIONS", "768")
        assert resolve_dimensions(None) == 768

    def test_explicit_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that explicit dimensions override environment."""
        monkeypatch.setenv("OGREP_DIMENSIONS", "768")
        assert resolve_dimensions(512) == 512

    def test_returns_none_when_no_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returning None when no dimension specified."""
        monkeypatch.delenv("OGREP_DIMENSIONS", raising=False)
        assert resolve_dimensions(None) is None


class TestGetModel:
    """Tests for get_model function."""

    def test_get_valid_model(self) -> None:
        """Test getting a valid model."""
        model = get_model("text-embedding-3-small")
        assert isinstance(model, EmbeddingModel)
        assert model.id == "text-embedding-3-small"
        assert model.dimensions == 1536

    def test_get_local_model(self) -> None:
        """Test getting a local model."""
        model = get_model("nomic-embed-text-v1.5")
        assert model.dimensions == 768
        assert model.price_per_million == 0.0

    def test_get_invalid_model_raises(self) -> None:
        """Test that invalid model ID raises KeyError."""
        with pytest.raises(KeyError):
            get_model("nonexistent-model")


class TestListModels:
    """Tests for list_models function."""

    def test_returns_list_of_models(self) -> None:
        """Test that list_models returns a list of EmbeddingModel."""
        models = list_models()
        assert isinstance(models, list)
        assert all(isinstance(m, EmbeddingModel) for m in models)

    def test_models_sorted_by_price(self) -> None:
        """Test that models are sorted by price (ascending)."""
        models = list_models()
        prices = [m.price_per_million for m in models]
        assert prices == sorted(prices)

    def test_includes_all_models(self) -> None:
        """Test that all defined models are included."""
        models = list_models()
        assert len(models) == len(MODELS)


class TestGetOptimalChunkLines:
    """Tests for get_optimal_chunk_lines function."""

    def test_env_var_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that OGREP_CHUNK_LINES environment variable takes precedence."""
        monkeypatch.setenv("OGREP_CHUNK_LINES", "45")
        assert get_optimal_chunk_lines("nomic") == 45
        assert get_optimal_chunk_lines("bge") == 45
        assert get_optimal_chunk_lines("small") == 45

    def test_model_specific_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test model-specific chunk size defaults."""
        monkeypatch.delenv("OGREP_CHUNK_LINES", raising=False)
        assert get_optimal_chunk_lines("nomic") == 30  # Updated per benchmark results
        assert get_optimal_chunk_lines("bge") == 30
        assert get_optimal_chunk_lines("minilm") == 30
        assert get_optimal_chunk_lines("small") == DEFAULT_CHUNK_LINES

    def test_uses_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that aliases work correctly."""
        monkeypatch.delenv("OGREP_CHUNK_LINES", raising=False)
        # "local" is an alias for nomic (30-line chunks per benchmark)
        assert get_optimal_chunk_lines("local") == 30

    def test_default_model_chunk_lines(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default chunk lines when no model specified."""
        monkeypatch.delenv("OGREP_CHUNK_LINES", raising=False)
        monkeypatch.delenv("OGREP_MODEL", raising=False)
        monkeypatch.delenv("OGREP_BASE_URL", raising=False)
        assert get_optimal_chunk_lines(None) == DEFAULT_CHUNK_LINES


class TestGetOptimalOverlap:
    """Tests for get_optimal_overlap function."""

    def test_env_var_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that OGREP_OVERLAP_LINES environment variable takes precedence."""
        monkeypatch.setenv("OGREP_OVERLAP_LINES", "20")
        assert get_optimal_overlap("nomic") == 20
        assert get_optimal_overlap("bge") == 20
        assert get_optimal_overlap("small") == 20

    def test_model_specific_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test model-specific overlap defaults."""
        monkeypatch.delenv("OGREP_OVERLAP_LINES", raising=False)
        assert get_optimal_overlap("nomic") == 15  # Nomic benefits from more overlap
        assert get_optimal_overlap("bge") == 5  # BGE prefers minimal overlap
        assert get_optimal_overlap("minilm") == 15  # MiniLM benefits from more overlap
        assert get_optimal_overlap("small") == DEFAULT_OVERLAP_LINES  # OpenAI uses default

    def test_uses_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that aliases work correctly."""
        monkeypatch.delenv("OGREP_OVERLAP_LINES", raising=False)
        # "local" is an alias for nomic (15-line overlap per benchmark)
        assert get_optimal_overlap("local") == 15

    def test_default_model_overlap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default overlap when no model specified."""
        monkeypatch.delenv("OGREP_OVERLAP_LINES", raising=False)
        monkeypatch.delenv("OGREP_MODEL", raising=False)
        monkeypatch.delenv("OGREP_BASE_URL", raising=False)
        assert get_optimal_overlap(None) == DEFAULT_OVERLAP_LINES


class TestFormatModelsTable:
    """Tests for format_models_table function."""

    def test_returns_string(self) -> None:
        """Test that format_models_table returns a string."""
        result = format_models_table()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_all_models(self) -> None:
        """Test that output includes all model IDs."""
        result = format_models_table()
        for model_id in MODELS:
            assert model_id in result

    def test_includes_configuration_info(self) -> None:
        """Test that output includes configuration instructions."""
        result = format_models_table()
        assert "OGREP_MODEL" in result
        assert "OGREP_DIMENSIONS" in result

    def test_includes_aliases(self) -> None:
        """Test that output includes alias information."""
        result = format_models_table()
        assert "small" in result and "text-embedding-3-small" in result
        assert "large" in result and "text-embedding-3-large" in result

    def test_includes_local_setup_instructions(self) -> None:
        """Test that output includes LM Studio setup."""
        result = format_models_table()
        assert "LM Studio" in result
        assert "lms server start" in result


class TestModelAliases:
    """Tests for MODEL_ALIASES consistency."""

    def test_all_aliases_resolve_to_valid_models(self) -> None:
        """Test that all aliases point to valid model IDs."""
        for alias, model_id in MODEL_ALIASES.items():
            assert model_id in MODELS, f"Alias '{alias}' points to invalid model '{model_id}'"

    def test_alias_count(self) -> None:
        """Test that we have expected number of aliases."""
        assert len(MODEL_ALIASES) >= 7  # small, large, ada, bge, nomic, minilm, local


class TestEmbeddingModelDataclass:
    """Tests for EmbeddingModel dataclass."""

    def test_model_attributes(self) -> None:
        """Test that models have expected attributes."""
        model = MODELS["text-embedding-3-small"]
        assert model.id == "text-embedding-3-small"
        assert model.name == "Text Embedding 3 Small"
        assert model.dimensions == 1536
        assert model.price_per_million == 0.02
        assert len(model.use_cases) > 0

    def test_local_model_attributes(self) -> None:
        """Test local model specific attributes."""
        model = MODELS["nomic-embed-text-v1.5"]
        assert model.price_per_million == 0.0
        assert model.optimal_chunk_lines == 30  # Updated per benchmark results
        assert "Local" in model.name

    def test_model_is_frozen(self) -> None:
        """Test that EmbeddingModel is immutable."""
        model = MODELS["text-embedding-3-small"]
        with pytest.raises(AttributeError):  # Frozen dataclass
            model.dimensions = 999  # type: ignore[misc]
