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
