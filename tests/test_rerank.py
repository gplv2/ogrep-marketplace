"""
Tests for cross-encoder reranking functionality.

These tests verify the reranking module that uses cross-encoder models
to improve search result ordering.
"""

import pytest
from dataclasses import dataclass
from unittest.mock import Mock, patch, MagicMock

# We'll test the rerank module once created
# For now, define expected interfaces


@dataclass
class MockHit:
    """Mock Hit for testing without importing from search."""

    score: float
    path: str
    start_line: int
    end_line: int
    text: str
    chunk_id: int
    chunk_index: int
    confidence: str


class TestRerankerAvailability:
    """Test reranker availability detection."""

    def test_reranker_not_available_without_sentence_transformers(self):
        """Reranker should report unavailable if sentence-transformers not installed."""
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            # Force reimport
            import importlib

            try:
                from ogrep import rerank

                importlib.reload(rerank)
                assert not rerank.is_reranker_available()
            except ImportError:
                # Expected if module checks at import time
                pass

    def test_reranker_available_with_sentence_transformers(self):
        """Reranker should report available when sentence-transformers is installed."""
        mock_st = MagicMock()
        with patch.dict("sys.modules", {"sentence_transformers": mock_st}):
            from ogrep import rerank

            # Should not raise
            assert hasattr(rerank, "is_reranker_available")


class TestRerankerFunction:
    """Test the rerank_results function."""

    def test_rerank_returns_same_count_or_less(self):
        """Reranking should return at most the same number of results."""
        from ogrep.rerank import rerank_results

        hits = [
            MockHit(
                score=0.5,
                path="/test.py",
                start_line=1,
                end_line=10,
                text="def foo(): pass",
                chunk_id=1,
                chunk_index=0,
                confidence="medium",
            ),
            MockHit(
                score=0.4,
                path="/test.py",
                start_line=11,
                end_line=20,
                text="def bar(): pass",
                chunk_id=2,
                chunk_index=1,
                confidence="low",
            ),
        ]

        with patch("ogrep.rerank._get_reranker") as mock_reranker:
            mock_model = MagicMock()
            mock_model.predict.return_value = [0.8, 0.6]
            mock_reranker.return_value = mock_model

            result = rerank_results("test query", hits)
            assert len(result) <= len(hits)

    def test_rerank_reorders_by_cross_encoder_score(self):
        """Results should be reordered by cross-encoder scores."""
        from ogrep.rerank import rerank_results

        hits = [
            MockHit(
                score=0.5,
                path="/test.py",
                start_line=1,
                end_line=10,
                text="first result",
                chunk_id=1,
                chunk_index=0,
                confidence="medium",
            ),
            MockHit(
                score=0.4,
                path="/test.py",
                start_line=11,
                end_line=20,
                text="second result - better match",
                chunk_id=2,
                chunk_index=1,
                confidence="low",
            ),
        ]

        with patch("ogrep.rerank._get_reranker") as mock_reranker:
            mock_model = MagicMock()
            # Second result scores higher with reranker
            mock_model.predict.return_value = [0.3, 0.9]
            mock_reranker.return_value = mock_model

            result = rerank_results("test query", hits)

            # Second hit should now be first
            assert result[0].text == "second result - better match"
            assert result[1].text == "first result"

    def test_rerank_updates_scores(self):
        """Reranked results should have updated scores from cross-encoder."""
        from ogrep.rerank import rerank_results

        hits = [
            MockHit(
                score=0.5,
                path="/test.py",
                start_line=1,
                end_line=10,
                text="test content",
                chunk_id=1,
                chunk_index=0,
                confidence="medium",
            ),
        ]

        with patch("ogrep.rerank._get_reranker") as mock_reranker:
            mock_model = MagicMock()
            mock_model.predict.return_value = [0.95]
            mock_reranker.return_value = mock_model

            result = rerank_results("test query", hits)

            # Score should be updated to reranker score
            assert result[0].score == pytest.approx(0.95)

    def test_rerank_respects_top_n_parameter(self):
        """Should only rerank top_n candidates."""
        from ogrep.rerank import rerank_results

        hits = [
            MockHit(
                score=0.5 - i * 0.1,
                path="/test.py",
                start_line=i * 10 + 1,
                end_line=(i + 1) * 10,
                text=f"result {i}",
                chunk_id=i,
                chunk_index=i,
                confidence="medium",
            )
            for i in range(10)
        ]

        with patch("ogrep.rerank._get_reranker") as mock_reranker:
            mock_model = MagicMock()
            # Only 3 scores for top_n=3
            mock_model.predict.return_value = [0.9, 0.8, 0.7]
            mock_reranker.return_value = mock_model

            result = rerank_results("test query", hits, top_n=3)

            # Should have called predict with only 3 pairs
            call_args = mock_model.predict.call_args[0][0]
            assert len(call_args) == 3

    def test_rerank_empty_list(self):
        """Should handle empty hit list gracefully."""
        from ogrep.rerank import rerank_results

        result = rerank_results("test query", [])
        assert result == []

    def test_rerank_single_result(self):
        """Should handle single result."""
        from ogrep.rerank import rerank_results

        hits = [
            MockHit(
                score=0.5,
                path="/test.py",
                start_line=1,
                end_line=10,
                text="only result",
                chunk_id=1,
                chunk_index=0,
                confidence="medium",
            ),
        ]

        with patch("ogrep.rerank._get_reranker") as mock_reranker:
            mock_model = MagicMock()
            mock_model.predict.return_value = [0.8]
            mock_reranker.return_value = mock_model

            result = rerank_results("test query", hits)
            assert len(result) == 1


class TestRerankerModel:
    """Test reranker model loading and caching."""

    def test_model_is_cached(self):
        """Model should be loaded once and cached."""
        from ogrep import rerank
        from ogrep.rerank import _get_reranker, _clear_reranker_cache

        _clear_reranker_cache()

        mock_ce_class = MagicMock()
        mock_model = MagicMock()
        mock_ce_class.return_value = mock_model

        # Patch the module-level CrossEncoder
        original_ce = rerank.CrossEncoder
        try:
            rerank.CrossEncoder = mock_ce_class

            # First call loads model
            model1 = _get_reranker()
            # Second call should use cache
            model2 = _get_reranker()

            assert mock_ce_class.call_count == 1
            assert model1 is model2
        finally:
            rerank.CrossEncoder = original_ce
            _clear_reranker_cache()

    def test_custom_model_from_env(self):
        """Should use model from OGREP_RERANK_MODEL env var."""
        from ogrep import rerank
        from ogrep.rerank import _get_reranker, _clear_reranker_cache

        _clear_reranker_cache()

        mock_ce_class = MagicMock()
        mock_model = MagicMock()
        mock_ce_class.return_value = mock_model

        original_ce = rerank.CrossEncoder
        try:
            rerank.CrossEncoder = mock_ce_class

            with patch.dict("os.environ", {"OGREP_RERANK_MODEL": "custom/model"}):
                _get_reranker()

                mock_ce_class.assert_called_once_with("custom/model")
        finally:
            rerank.CrossEncoder = original_ce
            _clear_reranker_cache()


class TestRerankerConfidence:
    """Test confidence level updates after reranking."""

    def test_confidence_updated_after_rerank(self):
        """Confidence levels should be recalculated after reranking."""
        from ogrep.rerank import rerank_results

        hits = [
            MockHit(
                score=0.3,
                path="/test.py",
                start_line=1,
                end_line=10,
                text="low confidence originally",
                chunk_id=1,
                chunk_index=0,
                confidence="low",
            ),
        ]

        with patch("ogrep.rerank._get_reranker") as mock_reranker:
            mock_model = MagicMock()
            mock_model.predict.return_value = [0.95]  # High reranker score
            mock_reranker.return_value = mock_model

            result = rerank_results("test query", hits)

            # Confidence should be updated based on new score
            assert result[0].confidence == "high"


class TestRerankerEnvironmentConfig:
    """Test environment variable configuration."""

    def test_default_top_n(self):
        """Default top_n should be 50 from OGREP_RERANK_TOPN."""
        from ogrep.rerank import DEFAULT_RERANK_TOPN

        assert DEFAULT_RERANK_TOPN == 50

    def test_default_model(self):
        """Default model should be BAAI/bge-reranker-v2-m3."""
        from ogrep.rerank import DEFAULT_RERANK_MODEL

        assert DEFAULT_RERANK_MODEL == "BAAI/bge-reranker-v2-m3"
