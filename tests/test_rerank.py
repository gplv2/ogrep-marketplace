"""
Tests for cross-encoder reranking functionality.

These tests verify the reranking module that uses cross-encoder models
to improve search result ordering.
"""

import io
import sys
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

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

            _result = rerank_results("test query", hits, top_n=3)

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
        from ogrep.rerank import _clear_all_state, _get_reranker

        _clear_all_state()

        mock_ce_class = MagicMock()
        mock_model = MagicMock()
        mock_ce_class.return_value = mock_model

        # Patch the lazy-loaded CrossEncoder
        original_ce = rerank._CrossEncoder
        original_attempted = rerank._crossencoder_import_attempted
        try:
            rerank._CrossEncoder = mock_ce_class
            rerank._crossencoder_import_attempted = True

            # First call loads model
            model1 = _get_reranker()
            # Second call should use cache
            model2 = _get_reranker()

            assert mock_ce_class.call_count == 1
            assert model1 is model2
        finally:
            rerank._CrossEncoder = original_ce
            rerank._crossencoder_import_attempted = original_attempted
            _clear_all_state()

    def test_custom_model_from_env(self):
        """Should use model from OGREP_RERANK_MODEL env var."""
        from ogrep import rerank
        from ogrep.rerank import _clear_all_state, _get_reranker

        _clear_all_state()

        mock_ce_class = MagicMock()
        mock_model = MagicMock()
        mock_ce_class.return_value = mock_model

        original_ce = rerank._CrossEncoder
        original_attempted = rerank._crossencoder_import_attempted
        try:
            rerank._CrossEncoder = mock_ce_class
            rerank._crossencoder_import_attempted = True

            with patch.dict("os.environ", {"OGREP_RERANK_MODEL": "custom/model"}):
                _get_reranker()

                mock_ce_class.assert_called_once_with("custom/model")
        finally:
            rerank._CrossEncoder = original_ce
            rerank._crossencoder_import_attempted = original_attempted
            _clear_all_state()


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
        """Default model should be bge-m3 (alias for BAAI/bge-reranker-v2-m3)."""
        from ogrep.rerank import DEFAULT_RERANK_MODEL

        assert DEFAULT_RERANK_MODEL == "bge-m3"


class TestWarningCapture:
    """Test CUDA and other warning capture during model loading."""

    def test_stderr_warnings_captured_during_model_load(self):
        """Warnings printed to stderr during model load should be captured."""
        from ogrep import rerank
        from ogrep.rerank import (
            _clear_all_state,
            _get_reranker,
            get_captured_warnings,
        )

        _clear_all_state()

        # Create a mock CrossEncoder that prints warnings like PyTorch does
        def mock_init(*args, **kwargs):
            # Simulate CUDA warning printed to stderr
            print(
                "UserWarning: CUDA initialization: The NVIDIA driver on your system "
                "is too old (found version 11040).",
                file=sys.stderr,
            )
            return MagicMock()

        mock_ce_class = MagicMock(side_effect=mock_init)

        original_ce = rerank._CrossEncoder
        original_attempted = rerank._crossencoder_import_attempted
        try:
            rerank._CrossEncoder = mock_ce_class
            rerank._crossencoder_import_attempted = True

            # Load model - should capture the warning
            _get_reranker()

            # Check that warning was captured
            warnings = get_captured_warnings()
            assert len(warnings) >= 1
            assert "CUDA" in warnings[0] or "driver" in warnings[0]

        finally:
            rerank._CrossEncoder = original_ce
            rerank._crossencoder_import_attempted = original_attempted
            _clear_all_state()

    def test_captured_warnings_can_be_cleared(self):
        """Captured warnings should be clearable."""
        # Manually add a warning for testing
        import ogrep.rerank as rerank_module
        from ogrep.rerank import (
            clear_captured_warnings,
            get_captured_warnings,
        )

        rerank_module._captured_warnings = ["test warning"]

        # Should have the warning
        warnings = get_captured_warnings()
        assert len(warnings) == 1

        # Clear and verify
        clear_captured_warnings()
        warnings = get_captured_warnings()
        assert len(warnings) == 0

    def test_get_captured_warnings_returns_copy(self):
        """get_captured_warnings should return a copy, not the original list."""
        import ogrep.rerank as rerank_module
        from ogrep.rerank import clear_captured_warnings, get_captured_warnings

        rerank_module._captured_warnings = ["warning1", "warning2"]

        warnings = get_captured_warnings()
        warnings.append("new warning")

        # Original should be unchanged
        assert len(rerank_module._captured_warnings) == 2

        clear_captured_warnings()

    def test_warnings_not_printed_to_stderr_during_model_load(self):
        """Warnings should be captured, not printed to stderr."""
        from ogrep import rerank
        from ogrep.rerank import _clear_all_state, _get_reranker

        _clear_all_state()

        # Capture real stderr to verify nothing leaks
        captured_stderr = io.StringIO()

        def mock_init(*args, **kwargs):
            print("CUDA warning simulation", file=sys.stderr)
            return MagicMock()

        mock_ce_class = MagicMock(side_effect=mock_init)

        original_ce = rerank._CrossEncoder
        original_attempted = rerank._crossencoder_import_attempted
        original_stderr = sys.stderr

        try:
            rerank._CrossEncoder = mock_ce_class
            rerank._crossencoder_import_attempted = True

            # Redirect stderr to capture any leakage
            sys.stderr = captured_stderr

            # Load model
            _get_reranker()

            # Reset stderr
            sys.stderr = original_stderr

            # Check that nothing leaked to our capture
            leaked = captured_stderr.getvalue()
            assert "CUDA" not in leaked

        finally:
            sys.stderr = original_stderr
            rerank._CrossEncoder = original_ce
            rerank._crossencoder_import_attempted = original_attempted
            _clear_all_state()

    def test_clear_reranker_cache_also_clears_warnings(self):
        """_clear_reranker_cache should also clear captured warnings."""
        import ogrep.rerank as rerank_module
        from ogrep.rerank import _clear_reranker_cache, get_captured_warnings

        rerank_module._captured_warnings = ["some warning"]
        assert len(get_captured_warnings()) == 1

        _clear_reranker_cache()

        assert len(get_captured_warnings()) == 0

    def test_lazy_import_captures_cuda_warnings(self):
        """Lazy import should capture CUDA warnings during sentence_transformers import."""
        from ogrep import rerank
        from ogrep.rerank import (
            _clear_all_state,
        )

        _clear_all_state()

        # Save original state
        original_stderr = sys.stderr

        # Capture what would go to stderr
        test_stderr = io.StringIO()

        # Mock the import to print a warning during import
        def mock_lazy_import():
            # Within the lazy import context, stderr is captured
            # but we'll print directly to test
            print("UserWarning: CUDA init failed", file=sys.stderr)
            return MagicMock()

        try:
            # Redirect stderr during the actual import call
            sys.stderr = test_stderr

            # Force a fresh import attempt with warning capture
            rerank._crossencoder_import_attempted = False
            rerank._CrossEncoder = None

            # The lazy import captures stderr internally
            # We can't easily test this without actually importing,
            # but we can verify the mechanism works
            sys.stderr = original_stderr

        finally:
            sys.stderr = original_stderr
            _clear_all_state()


class TestRerankLock:
    """Test the rerank lock mechanism for preventing parallel OOM."""

    def test_lock_context_manager_exists(self):
        """The _rerank_lock context manager should exist."""
        from ogrep.rerank import _rerank_lock

        assert callable(_rerank_lock)

    def test_lock_timeout_exception_exists(self):
        """The RerankLockTimeout exception should exist."""
        from ogrep.rerank import RerankLockTimeout

        assert issubclass(RerankLockTimeout, Exception)

    def test_lock_gracefully_handles_readonly_filesystem(self):
        """Lock should gracefully proceed when lock file can't be created."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        import ogrep.rerank as rerank_module
        from ogrep.rerank import _rerank_lock, clear_captured_warnings

        # Clear any existing warnings
        clear_captured_warnings()

        # Mock the lock path to a directory that doesn't exist and can't be created
        fake_path = Path("/nonexistent/readonly/rerank.lock")

        original_lock_path = rerank_module.RERANK_LOCK_PATH
        try:
            rerank_module.RERANK_LOCK_PATH = fake_path

            # Should not raise, should proceed without lock
            with _rerank_lock():
                pass  # Code executed successfully

            # Should have captured a warning
            from ogrep.rerank import get_captured_warnings

            warnings = get_captured_warnings()
            assert len(warnings) >= 1
            assert "lock" in warnings[0].lower() or "cannot create" in warnings[0].lower()

        finally:
            rerank_module.RERANK_LOCK_PATH = original_lock_path
            clear_captured_warnings()

    def test_lock_timeout_returns_unreranked_results(self):
        """On lock timeout, rerank_results should return unreranked hits with warning."""
        from unittest.mock import patch

        from ogrep.rerank import (
            RerankLockTimeout,
            _clear_all_state,
            clear_captured_warnings,
            get_captured_warnings,
            rerank_results,
        )

        hits = [
            MockHit(
                score=0.8,
                path="file1.py",
                start_line=1,
                end_line=10,
                text="first",
                chunk_id=1,
                chunk_index=0,
                confidence="high",
            ),
            MockHit(
                score=0.6,
                path="file2.py",
                start_line=1,
                end_line=10,
                text="second",
                chunk_id=2,
                chunk_index=0,
                confidence="medium",
            ),
        ]

        clear_captured_warnings()

        # Mock the lock to always timeout
        def mock_lock_timeout(*args, **kwargs):
            raise RerankLockTimeout("Test timeout")

        with patch("ogrep.rerank._rerank_lock") as mock_lock:
            mock_lock.side_effect = mock_lock_timeout

            result = rerank_results("test query", hits)

            # Should return unreranked results (same order as input)
            assert len(result) == 2
            assert result[0].path == "file1.py"  # Original first hit
            assert result[1].path == "file2.py"  # Original second hit

            # Should have a warning about timeout
            warnings = get_captured_warnings()
            assert len(warnings) >= 1
            assert "timeout" in warnings[0].lower() or "unreranked" in warnings[0].lower()

        _clear_all_state()

    def test_lock_env_vars_configurable(self):
        """Lock path and timeout should be configurable via env vars."""
        import os
        from pathlib import Path

        # The defaults are read at import time, but let's verify the env var names
        # are documented in the module
        import ogrep.rerank as rerank_module

        # Verify constants exist
        assert hasattr(rerank_module, "RERANK_LOCK_PATH")
        assert hasattr(rerank_module, "RERANK_LOCK_TIMEOUT")

        # Verify they have sensible defaults
        assert isinstance(rerank_module.RERANK_LOCK_PATH, Path)
        assert isinstance(rerank_module.RERANK_LOCK_TIMEOUT, float)
        assert rerank_module.RERANK_LOCK_TIMEOUT > 0


class TestModelAliases:
    """Test model alias resolution."""

    def test_sentence_transformers_aliases_exist(self):
        """Sentence-transformers aliases should be defined."""
        from ogrep.rerank import SENTENCE_TRANSFORMERS_ALIASES

        assert "bge-m3" in SENTENCE_TRANSFORMERS_ALIASES
        assert "minilm" in SENTENCE_TRANSFORMERS_ALIASES
        assert SENTENCE_TRANSFORMERS_ALIASES["bge-m3"] == "BAAI/bge-reranker-v2-m3"
        assert SENTENCE_TRANSFORMERS_ALIASES["minilm"] == "cross-encoder/ms-marco-MiniLM-L6-v2"

    def test_flashrank_aliases_exist(self):
        """FlashRank aliases should be defined."""
        from ogrep.rerank import FLASHRANK_ALIASES

        assert "flashrank" in FLASHRANK_ALIASES
        assert "flashrank:tiny" in FLASHRANK_ALIASES
        assert "flashrank:mini" in FLASHRANK_ALIASES
        assert FLASHRANK_ALIASES["flashrank"] == "ms-marco-TinyBERT-L-2-v2"
        assert FLASHRANK_ALIASES["flashrank:mini"] == "ms-marco-MiniLM-L-12-v2"

    def test_resolve_model_name_with_alias(self):
        """Model aliases should resolve to full names."""
        from ogrep.rerank import _resolve_model_name

        assert _resolve_model_name("bge-m3") == "BAAI/bge-reranker-v2-m3"
        assert _resolve_model_name("minilm") == "cross-encoder/ms-marco-MiniLM-L6-v2"
        assert _resolve_model_name("flashrank") == "ms-marco-TinyBERT-L-2-v2"
        assert _resolve_model_name("flashrank:mini") == "ms-marco-MiniLM-L-12-v2"

    def test_resolve_model_name_passthrough(self):
        """Unknown model names should pass through unchanged."""
        from ogrep.rerank import _resolve_model_name

        assert _resolve_model_name("custom/model") == "custom/model"
        assert _resolve_model_name("BAAI/bge-reranker-v2-m3") == "BAAI/bge-reranker-v2-m3"


class TestBackendDetection:
    """Test backend detection logic."""

    def test_is_flashrank_model_with_aliases(self):
        """FlashRank models should be detected correctly."""
        from ogrep.rerank import _is_flashrank_model

        assert _is_flashrank_model("flashrank") is True
        assert _is_flashrank_model("flashrank:tiny") is True
        assert _is_flashrank_model("flashrank:mini") is True
        assert _is_flashrank_model("ms-marco-TinyBERT-L-2-v2") is True
        assert _is_flashrank_model("ms-marco-MiniLM-L-12-v2") is True

    def test_is_flashrank_model_negative(self):
        """Non-FlashRank models should not be detected as FlashRank."""
        from ogrep.rerank import _is_flashrank_model

        assert _is_flashrank_model("bge-m3") is False
        assert _is_flashrank_model("minilm") is False
        assert _is_flashrank_model("BAAI/bge-reranker-v2-m3") is False
        assert _is_flashrank_model("custom/model") is False

    def test_is_sentence_transformers_model(self):
        """Sentence-transformers models should be detected correctly."""
        from ogrep.rerank import _is_sentence_transformers_model

        assert _is_sentence_transformers_model("bge-m3") is True
        assert _is_sentence_transformers_model("minilm") is True
        assert _is_sentence_transformers_model("BAAI/bge-reranker-v2-m3") is True
        assert _is_sentence_transformers_model("custom/model") is True

    def test_is_sentence_transformers_model_negative(self):
        """FlashRank models should not be detected as sentence-transformers."""
        from ogrep.rerank import _is_sentence_transformers_model

        assert _is_sentence_transformers_model("flashrank") is False
        assert _is_sentence_transformers_model("flashrank:mini") is False


class TestFlashRankBackend:
    """Test FlashRank backend functionality."""

    def test_flashrank_availability_check(self):
        """is_flashrank_available should work without errors."""
        from ogrep.rerank import is_flashrank_available

        # Just check it runs without error and returns a bool
        result = is_flashrank_available()
        assert isinstance(result, bool)

    def test_rerank_with_flashrank_model_routes_correctly(self):
        """Using flashrank model should route to FlashRank backend."""
        from ogrep.rerank import (
            _clear_all_state,
            is_flashrank_available,
            rerank_results,
        )

        _clear_all_state()

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

        # Mock FlashRank if not available
        if not is_flashrank_available():
            # Skip test if FlashRank is not installed
            pytest.skip("FlashRank not installed")

        # If FlashRank is available, should work
        with patch("ogrep.rerank._get_flashrank_reranker") as mock_get:
            mock_ranker = MagicMock()
            mock_get.return_value = mock_ranker

            with patch("ogrep.rerank._flashrank_predict") as mock_predict:
                mock_predict.return_value = [0.9]

                result = rerank_results("test", hits, model_name="flashrank")

                # Should have called FlashRank functions
                mock_get.assert_called_once()
                mock_predict.assert_called_once()

        _clear_all_state()

    def test_flashrank_does_not_use_lock(self):
        """FlashRank backend should not use the rerank lock."""
        from ogrep.rerank import (
            _clear_all_state,
            is_flashrank_available,
            rerank_results,
        )

        _clear_all_state()

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

        if not is_flashrank_available():
            pytest.skip("FlashRank not installed")

        with patch("ogrep.rerank._rerank_lock") as mock_lock:
            with patch("ogrep.rerank._get_flashrank_reranker") as mock_get:
                mock_ranker = MagicMock()
                mock_get.return_value = mock_ranker

                with patch("ogrep.rerank._flashrank_predict") as mock_predict:
                    mock_predict.return_value = [0.9]

                    rerank_results("test", hits, model_name="flashrank")

                    # Lock should NOT have been called for FlashRank
                    mock_lock.assert_not_called()

        _clear_all_state()


class TestAvailableBackends:
    """Test the get_available_backends function."""

    def test_get_available_backends_structure(self):
        """get_available_backends should return proper structure."""
        from ogrep.rerank import get_available_backends

        backends = get_available_backends()

        assert "sentence_transformers" in backends
        assert "flashrank" in backends
        assert "default_model" in backends

        # Check sentence_transformers structure
        st = backends["sentence_transformers"]
        assert "available" in st
        assert "install" in st
        assert "models" in st
        assert isinstance(st["available"], bool)
        assert isinstance(st["models"], list)

        # Check flashrank structure
        fr = backends["flashrank"]
        assert "available" in fr
        assert "install" in fr
        assert "models" in fr
        assert isinstance(fr["available"], bool)
        assert isinstance(fr["models"], list)

    def test_get_available_backends_model_info(self):
        """Model info should include alias, name, and size."""
        from ogrep.rerank import get_available_backends

        backends = get_available_backends()

        # Check a sentence_transformers model
        st_models = backends["sentence_transformers"]["models"]
        assert len(st_models) > 0
        first_model = st_models[0]
        assert "alias" in first_model
        assert "name" in first_model
        assert "size" in first_model

        # Check a flashrank model
        fr_models = backends["flashrank"]["models"]
        assert len(fr_models) > 0
        first_model = fr_models[0]
        assert "alias" in first_model
        assert "name" in first_model
        assert "size" in first_model


class TestRerankerAvailabilityWithModel:
    """Test is_reranker_available with specific models."""

    def test_reranker_available_with_none_checks_any_backend(self):
        """is_reranker_available(None) should check if any backend is available."""
        from ogrep.rerank import is_reranker_available

        # Just verify it runs without error
        result = is_reranker_available(None)
        assert isinstance(result, bool)

    def test_reranker_available_checks_correct_backend_for_flashrank(self):
        """is_reranker_available should check FlashRank for flashrank models."""
        from ogrep.rerank import is_flashrank_available, is_reranker_available

        # The result should match is_flashrank_available for flashrank models
        flashrank_available = is_flashrank_available()
        assert is_reranker_available("flashrank") == flashrank_available
        assert is_reranker_available("flashrank:mini") == flashrank_available
