"""Tests for ogrep.embed module."""

from __future__ import annotations

import array
import math

import pytest

from ogrep.embed import _l2_normalize, embed_texts


class TestL2Normalize:
    """Tests for _l2_normalize function."""

    def test_normalize_unit_vector(self) -> None:
        """Test normalizing an already-unit vector."""
        vec = [1.0, 0.0, 0.0]
        result = _l2_normalize(vec)
        assert result == [1.0, 0.0, 0.0]

    def test_normalize_simple_vector(self) -> None:
        """Test normalizing a simple vector."""
        vec = [3.0, 4.0]  # 3-4-5 triangle
        result = _l2_normalize(vec)
        assert abs(result[0] - 0.6) < 1e-10
        assert abs(result[1] - 0.8) < 1e-10

    def test_normalized_vector_has_unit_length(self) -> None:
        """Test that normalized vector has length 1."""
        vec = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _l2_normalize(vec)
        length = math.sqrt(sum(x * x for x in result))
        assert abs(length - 1.0) < 1e-10

    def test_normalize_all_zeros(self) -> None:
        """Test normalizing a zero vector (edge case)."""
        vec = [0.0, 0.0, 0.0]
        result = _l2_normalize(vec)
        # Should not crash, returns zeros
        assert result == [0.0, 0.0, 0.0]

    def test_normalize_negative_values(self) -> None:
        """Test normalizing vector with negative values."""
        vec = [-3.0, 4.0]
        result = _l2_normalize(vec)
        assert abs(result[0] - (-0.6)) < 1e-10
        assert abs(result[1] - 0.8) < 1e-10

    def test_normalize_preserves_direction(self) -> None:
        """Test that normalization preserves direction."""
        vec = [2.0, 4.0, 6.0]
        result = _l2_normalize(vec)
        # Ratios should be preserved
        assert abs(result[1] / result[0] - 2.0) < 1e-10
        assert abs(result[2] / result[0] - 3.0) < 1e-10

    def test_normalize_large_vector(self) -> None:
        """Test normalizing a large vector (like embeddings)."""
        vec = [float(i) for i in range(256)]
        result = _l2_normalize(vec)
        length = math.sqrt(sum(x * x for x in result))
        assert abs(length - 1.0) < 1e-10


class TestEmbedTexts:
    """Tests for embed_texts function (uses mocked OpenAI)."""

    def test_embed_single_text(self) -> None:
        """Test embedding a single text."""
        blobs, dim = embed_texts(["Hello world"])
        assert len(blobs) == 1
        assert isinstance(blobs[0], bytes)
        assert dim > 0

    def test_embed_multiple_texts(self) -> None:
        """Test embedding multiple texts."""
        texts = ["Hello", "World", "Test"]
        blobs, dim = embed_texts(texts)
        assert len(blobs) == 3
        assert all(isinstance(b, bytes) for b in blobs)

    def test_embeddings_are_float32(self) -> None:
        """Test that embeddings are stored as float32."""
        blobs, dim = embed_texts(["Test text"])
        # float32 is 4 bytes per value
        assert len(blobs[0]) == dim * 4

    def test_embeddings_can_be_decoded(self) -> None:
        """Test that embeddings can be decoded back to floats."""
        blobs, dim = embed_texts(["Test"])
        arr = array.array("f")
        arr.frombytes(blobs[0])
        assert len(arr) == dim
        assert all(isinstance(x, float) for x in arr)

    def test_different_texts_different_embeddings(self) -> None:
        """Test that different texts produce different embeddings."""
        blobs, _ = embed_texts(["Hello", "Goodbye"])
        assert blobs[0] != blobs[1]

    def test_same_text_same_embedding(self) -> None:
        """Test that same text produces same embedding."""
        blobs1, _ = embed_texts(["Hello world"])
        blobs2, _ = embed_texts(["Hello world"])
        assert blobs1[0] == blobs2[0]

    def test_embeddings_are_normalized(self) -> None:
        """Test that returned embeddings are L2-normalized."""
        blobs, dim = embed_texts(["Test normalization"])
        arr = array.array("f")
        arr.frombytes(blobs[0])
        length = math.sqrt(sum(x * x for x in arr))
        assert abs(length - 1.0) < 1e-5  # float32 precision

    def test_with_model_alias(self) -> None:
        """Test embedding with model alias."""
        blobs, dim = embed_texts(["Test"], model="small")
        assert len(blobs) == 1
        assert dim > 0

    def test_with_explicit_model(self) -> None:
        """Test embedding with explicit model ID."""
        blobs, dim = embed_texts(["Test"], model="text-embedding-3-small")
        assert len(blobs) == 1

    def test_with_local_model_alias(self) -> None:
        """Test embedding with local model alias."""
        blobs, dim = embed_texts(["Test"], model="nomic")
        assert len(blobs) == 1

    def test_empty_list_returns_empty(self) -> None:
        """Test that embedding empty list returns empty results."""
        blobs, dim = embed_texts([])
        assert blobs == []
        assert dim == 0

    def test_embedding_with_dimensions(self) -> None:
        """Test embedding with explicit dimensions parameter."""
        # This tests the parameter passing, actual dimension depends on mock
        blobs, dim = embed_texts(["Test"], dimensions=512)
        assert len(blobs) == 1


class TestEmbedTextsWithEnv:
    """Tests for embed_texts with environment variable configuration."""

    def test_uses_env_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that OGREP_MODEL env var is used."""
        monkeypatch.setenv("OGREP_MODEL", "large")
        # Should not raise - mock handles any model
        blobs, dim = embed_texts(["Test"])
        assert len(blobs) == 1

    def test_base_url_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that OGREP_BASE_URL is respected (for local servers)."""
        monkeypatch.setenv("OGREP_BASE_URL", "http://localhost:1234/v1")
        # Should not raise - mock handles the custom client
        blobs, dim = embed_texts(["Test"], model="nomic")
        assert len(blobs) == 1


class TestEmbedTextsErrorHandling:
    """Tests for embed_texts error handling."""

    def test_invalid_model_raises(self) -> None:
        """Test that invalid model raises ValueError."""
        with pytest.raises(ValueError, match="Unknown model"):
            embed_texts(["Test"], model="nonexistent-model")


class TestTokenEstimation:
    """Tests for token estimation function."""

    def test_estimate_tokens_simple(self) -> None:
        """Test token estimation for simple text."""
        from ogrep.embed import _estimate_tokens

        # Rough estimate: ~4 chars per token for code
        text = "def hello():"  # 12 chars
        tokens = _estimate_tokens(text)
        # Should be roughly 3 tokens (12 / 4)
        assert 2 <= tokens <= 6

    def test_estimate_tokens_empty(self) -> None:
        """Test token estimation for empty text."""
        from ogrep.embed import _estimate_tokens

        assert _estimate_tokens("") == 0

    def test_estimate_tokens_code_block(self) -> None:
        """Test token estimation for realistic code."""
        from ogrep.embed import _estimate_tokens

        code = """def authenticate_user(username: str, password: str) -> bool:
    \"\"\"Authenticate a user with username and password.\"\"\"
    if not username or not password:
        return False
    return check_credentials(username, password)
"""
        tokens = _estimate_tokens(code)
        # ~250 chars should be ~60-80 tokens
        assert 50 <= tokens <= 100


class TestTokenAwareBatching:
    """Tests for token-aware batching."""

    def test_batch_splits_on_token_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that batches are split when total tokens exceed context limit."""
        from ogrep.embed import _create_token_aware_batches, _estimate_tokens

        # Create texts that together exceed the context limit
        # Each text is ~100 chars = ~25 tokens
        big_text = "x" * 400  # ~100 tokens
        texts = [big_text] * 100  # Total: ~10,000 tokens

        # With 8192 token limit, should split into multiple batches
        batches = _create_token_aware_batches(texts, max_tokens=8192)

        # Should have multiple batches
        assert len(batches) > 1
        # All texts should be included
        assert sum(len(b) for b in batches) == 100
        # Each batch should be under token limit
        for batch in batches:
            batch_tokens = sum(_estimate_tokens(t) for t in batch)
            assert batch_tokens <= 8192

    def test_batch_respects_count_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that batches respect max count even if under token limit."""
        from ogrep.embed import _create_token_aware_batches

        # Small texts that won't exceed token limit
        texts = ["hello"] * 100

        # With max_count=20, should split into batches of 20
        batches = _create_token_aware_batches(texts, max_tokens=8192, max_count=20)

        # Each batch should have at most 20 items
        for batch in batches:
            assert len(batch) <= 20
        # All texts should be included
        assert sum(len(b) for b in batches) == 100

    def test_oversized_single_chunk_is_truncated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a single chunk exceeding context is truncated with warning."""
        import warnings

        from ogrep.embed import _create_token_aware_batches

        # Create a single text that exceeds the context limit
        huge_text = "x" * 40000  # ~10,000 tokens

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            batches = _create_token_aware_batches([huge_text], max_tokens=8192)

            # Should have 1 batch with 1 (truncated) text
            assert len(batches) == 1
            assert len(batches[0]) == 1
            # Text should be truncated
            assert len(batches[0][0]) < len(huge_text)
            # Should emit a warning
            assert len(w) == 1
            assert "truncated" in str(w[0].message).lower()

    def test_embed_texts_handles_large_batch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that embed_texts correctly handles batches that would exceed token limit."""
        # Create texts that would exceed the 8192 token limit if sent together
        # Each ~1000 chars = ~250 tokens, 40 texts = ~10,000 tokens
        large_text = "def function_" + "x" * 990 + "(): pass"
        texts = [f"{large_text}_{i}" for i in range(40)]

        # Should complete without error (batches split internally)
        blobs, dim = embed_texts(texts, model="small")

        assert len(blobs) == 40
        assert dim > 0


class TestVoyageAIEmbeddings:
    """Tests for Voyage AI embedding backend."""

    def test_is_voyage_model_detection(self) -> None:
        """Test Voyage model detection."""
        from ogrep.embed import _is_voyage_model

        # Should detect Voyage models
        assert _is_voyage_model("voyage-code-3") is True
        assert _is_voyage_model("voyage-3") is True
        assert _is_voyage_model("voyage-3-lite") is True
        assert _is_voyage_model("voyage") is True
        assert _is_voyage_model("voyage-code") is True

        # Should not detect non-Voyage models
        assert _is_voyage_model("text-embedding-3-small") is False
        assert _is_voyage_model("nomic") is False
        assert _is_voyage_model("small") is False

    def test_voyage_model_in_models_dict(self) -> None:
        """Test that Voyage models are defined in MODELS dict."""
        from ogrep.models import MODELS

        assert "voyage-code-3" in MODELS
        assert "voyage-3" in MODELS
        assert "voyage-3-lite" in MODELS

    def test_voyage_model_aliases(self) -> None:
        """Test that Voyage model aliases are defined."""
        from ogrep.models import MODEL_ALIASES

        assert "voyage" in MODEL_ALIASES
        assert "voyage-code" in MODEL_ALIASES
        assert "voyage-lite" in MODEL_ALIASES

        # Aliases should resolve correctly
        assert MODEL_ALIASES["voyage"] == "voyage-code-3"
        assert MODEL_ALIASES["voyage-code"] == "voyage-code-3"
        assert MODEL_ALIASES["voyage-lite"] == "voyage-3-lite"

    def test_voyage_model_has_correct_dimensions(self) -> None:
        """Test that Voyage models have correct dimension settings."""
        from ogrep.models import MODELS

        # voyage-code-3 is 1024D
        assert MODELS["voyage-code-3"].dimensions == 1024

        # voyage-3 is 1024D
        assert MODELS["voyage-3"].dimensions == 1024

        # voyage-3-lite is 512D
        assert MODELS["voyage-3-lite"].dimensions == 512

    def test_embed_voyage_with_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test Voyage embedding with mocked client."""
        from unittest.mock import MagicMock, patch

        # Create mock Voyage client and response
        mock_result = MagicMock()
        mock_result.embeddings = [
            [0.1, 0.2, 0.3],  # 3D for testing
            [0.4, 0.5, 0.6],
        ]

        mock_client = MagicMock()
        mock_client.embed.return_value = mock_result

        mock_voyageai = MagicMock()
        mock_voyageai.Client.return_value = mock_client

        # Set API key
        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        with patch.dict("sys.modules", {"voyageai": mock_voyageai}):
            from ogrep.embed import _embed_voyage

            blobs, dim = _embed_voyage(["text1", "text2"], "voyage-code-3")

            # Should return correct number of blobs
            assert len(blobs) == 2
            # Dimension should match embeddings
            assert dim == 3
            # Client should be called with correct params
            mock_client.embed.assert_called_once()
            call_kwargs = mock_client.embed.call_args.kwargs
            assert call_kwargs["texts"] == ["text1", "text2"]
            assert call_kwargs["model"] == "voyage-code-3"
            assert call_kwargs["input_type"] == "document"

    def test_voyage_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that Voyage embedding requires API key."""
        from unittest.mock import MagicMock, patch

        # Clear API key
        monkeypatch.delenv("VOYAGE_API_KEY", raising=False)

        mock_voyageai = MagicMock()

        with patch.dict("sys.modules", {"voyageai": mock_voyageai}):
            from ogrep.embed import _embed_voyage

            with pytest.raises(ValueError, match="VOYAGE_API_KEY"):
                _embed_voyage(["test"], "voyage-code-3")
