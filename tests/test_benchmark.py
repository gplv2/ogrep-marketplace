"""Tests for ogrep.commands.benchmark module."""

from __future__ import annotations

from pathlib import Path

import pytest

from ogrep.commands.benchmark import (
    BenchmarkResult,
    ModelReport,
    _detect_available_models,
    _extract_significant_lines,
    _format_results_table,
    _generate_recommendations,
    _get_model_alias,
)
from ogrep.models import MODELS


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_result_creation(self) -> None:
        """Test creating a BenchmarkResult instance."""
        result = BenchmarkResult(
            model="text-embedding-3-small",
            dimensions=1536,
            chunk_size=60,
            overlap=10,
            accuracy=0.92,
            hits=9,
            total_samples=10,
            embed_time_s=2.34,
            query_time_s=0.02,
            index_time_s=2.50,
        )
        assert result.model == "text-embedding-3-small"
        assert result.accuracy == 0.92
        assert result.hits == 9
        assert result.chunk_size == 60

    def test_result_is_frozen(self) -> None:
        """Test that BenchmarkResult is immutable."""
        result = BenchmarkResult(
            model="test",
            dimensions=768,
            chunk_size=30,
            overlap=5,
            accuracy=0.5,
            hits=5,
            total_samples=10,
            embed_time_s=1.0,
            query_time_s=0.01,
            index_time_s=1.1,
        )
        with pytest.raises(AttributeError):  # Frozen dataclass
            result.accuracy = 0.9  # type: ignore[misc]


class TestModelReport:
    """Tests for ModelReport dataclass."""

    def test_report_creation(self) -> None:
        """Test creating a ModelReport instance."""
        report = ModelReport(
            model="text-embedding-3-small",
            model_alias="small",
            dimensions=1536,
            best_chunk_size=60,
            best_overlap=10,
            best_accuracy=0.92,
            avg_embed_time=2.0,
            avg_query_time=0.02,
            avg_index_time=2.5,
        )
        assert report.model == "text-embedding-3-small"
        assert report.model_alias == "small"
        assert report.best_accuracy == 0.92

    def test_report_results_list(self) -> None:
        """Test that ModelReport can hold results."""
        result = BenchmarkResult(
            model="test",
            dimensions=768,
            chunk_size=30,
            overlap=5,
            accuracy=0.8,
            hits=8,
            total_samples=10,
            embed_time_s=1.0,
            query_time_s=0.01,
            index_time_s=1.1,
        )
        report = ModelReport(
            model="test",
            model_alias="test",
            dimensions=768,
            best_chunk_size=30,
            best_overlap=5,
            best_accuracy=0.8,
            avg_embed_time=1.0,
            avg_query_time=0.01,
            avg_index_time=1.1,
            all_results=[result],
        )
        assert len(report.all_results) == 1
        assert report.all_results[0].accuracy == 0.8


class TestGetModelAlias:
    """Tests for _get_model_alias function."""

    def test_returns_alias_for_known_model(self) -> None:
        """Test that known models return their short alias."""
        assert _get_model_alias("text-embedding-3-small") == "small"
        assert _get_model_alias("text-embedding-3-large") == "large"
        assert _get_model_alias("nomic-embed-text-v1.5") == "nomic"

    def test_returns_model_id_for_unknown(self) -> None:
        """Test that unknown models return the model ID."""
        assert _get_model_alias("unknown-model") == "unknown-model"


class TestDetectAvailableModels:
    """Tests for _detect_available_models function."""

    def test_no_env_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that no API key or base URL returns empty dict."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OGREP_BASE_URL", raising=False)
        available = _detect_available_models()
        assert available == {}

    def test_openai_key_enables_cloud_models(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that OPENAI_API_KEY enables cloud models."""
        monkeypatch.delenv("OGREP_BASE_URL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        available = _detect_available_models()
        assert "text-embedding-3-small" in available
        assert "text-embedding-3-large" in available

    def test_base_url_enables_local_models(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that OGREP_BASE_URL enables local models."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("OGREP_BASE_URL", "http://localhost:1234/v1")
        available = _detect_available_models()
        # Should include local models
        local_models = [m for m in available if MODELS[m].price_per_million == 0]
        assert len(local_models) > 0

    def test_both_env_vars_enable_all_models(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that both env vars enable all models."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OGREP_BASE_URL", "http://localhost:1234/v1")
        available = _detect_available_models()
        assert "text-embedding-3-small" in available
        # Should also have local models
        local_models = [m for m in available if MODELS[m].price_per_million == 0]
        assert len(local_models) > 0


class TestExtractSignificantLines:
    """Tests for _extract_significant_lines function."""

    def test_extracts_python_functions(self, temp_dir: Path) -> None:
        """Test extracting Python function definitions."""
        test_file = temp_dir / "test.py"
        test_file.write_text(
            """
def hello_world():
    pass

def process_data(x):
    return x
"""
        )
        samples = _extract_significant_lines(temp_dir, max_samples=10)
        assert len(samples) == 2
        assert any("hello_world" in s[3] for s in samples)
        assert any("process_data" in s[3] for s in samples)

    def test_extracts_python_classes(self, temp_dir: Path) -> None:
        """Test extracting Python class definitions."""
        test_file = temp_dir / "test.py"
        test_file.write_text(
            """
class MyClass:
    pass

class AnotherClass:
    def method(self):
        pass
"""
        )
        samples = _extract_significant_lines(temp_dir, max_samples=10)
        assert any("MyClass" in s[3] for s in samples)
        assert any("AnotherClass" in s[3] for s in samples)

    def test_skips_dunder_methods(self, temp_dir: Path) -> None:
        """Test that dunder methods are skipped."""
        test_file = temp_dir / "test.py"
        test_file.write_text(
            """
class MyClass:
    def __init__(self):
        pass

    def __str__(self):
        return "test"

    def regular_method(self):
        pass
"""
        )
        samples = _extract_significant_lines(temp_dir, max_samples=10)
        # Should find class and regular_method, but not __init__ or __str__
        queries = [s[3] for s in samples]
        assert not any("__init__" in q for q in queries)
        assert not any("__str__" in q for q in queries)

    def test_skips_test_functions(self, temp_dir: Path) -> None:
        """Test that test functions are skipped."""
        test_file = temp_dir / "test.py"
        test_file.write_text(
            """
def test_something():
    pass

def test_another():
    pass

def real_function():
    pass
"""
        )
        samples = _extract_significant_lines(temp_dir, max_samples=10)
        queries = [s[3] for s in samples]
        assert not any("test_something" in q for q in queries)
        assert any("real_function" in q for q in queries)

    def test_respects_max_samples(self, temp_dir: Path) -> None:
        """Test that max_samples limits results."""
        test_file = temp_dir / "test.py"
        lines = "\n".join(f"def func_{i}(): pass" for i in range(20))
        test_file.write_text(lines)
        samples = _extract_significant_lines(temp_dir, max_samples=5)
        assert len(samples) <= 5


class TestFormatResultsTable:
    """Tests for _format_results_table function."""

    def test_empty_reports(self) -> None:
        """Test formatting with no reports."""
        result = _format_results_table([])
        assert "RESULTS BY MODEL" in result

    def test_single_report(self) -> None:
        """Test formatting with one report."""
        report = ModelReport(
            model="text-embedding-3-small",
            model_alias="small",
            dimensions=1536,
            best_chunk_size=60,
            best_overlap=10,
            best_accuracy=0.92,
            avg_embed_time=2.0,
            avg_query_time=0.02,
            avg_index_time=2.5,
        )
        result = _format_results_table([report])
        assert "small" in result
        assert "1536" in result
        assert "0.92" in result

    def test_multiple_reports_sorted(self) -> None:
        """Test that reports are sorted by accuracy."""
        reports = [
            ModelReport(
                model="low",
                model_alias="low",
                dimensions=768,
                best_chunk_size=30,
                best_overlap=5,
                best_accuracy=0.5,
                avg_embed_time=1.0,
                avg_query_time=0.01,
                avg_index_time=1.1,
            ),
            ModelReport(
                model="high",
                model_alias="high",
                dimensions=768,
                best_chunk_size=60,
                best_overlap=10,
                best_accuracy=0.9,
                avg_embed_time=2.0,
                avg_query_time=0.02,
                avg_index_time=2.2,
            ),
        ]
        result = _format_results_table(reports)
        # High accuracy should appear before low
        high_pos = result.find("high")
        low_pos = result.find("low")
        assert high_pos < low_pos


class TestGenerateRecommendations:
    """Tests for _generate_recommendations function."""

    def test_empty_reports(self) -> None:
        """Test recommendations with no reports."""
        result = _generate_recommendations([])
        assert "No models tested" in result

    def test_single_report_recommendation(self) -> None:
        """Test recommendations with one report."""
        report = ModelReport(
            model="text-embedding-3-small",
            model_alias="small",
            dimensions=1536,
            best_chunk_size=60,
            best_overlap=10,
            best_accuracy=0.92,
            avg_embed_time=2.0,
            avg_query_time=0.02,
            avg_index_time=2.5,
        )
        result = _generate_recommendations([report])
        assert "BEST OVERALL" in result
        assert "small" in result
        assert "60" in result  # chunk size

    def test_includes_quick_setup(self) -> None:
        """Test that recommendations include quick setup."""
        report = ModelReport(
            model="nomic-embed-text-v1.5",
            model_alias="nomic",
            dimensions=768,
            best_chunk_size=90,
            best_overlap=15,
            best_accuracy=0.85,
            avg_embed_time=1.5,
            avg_query_time=0.01,
            avg_index_time=1.7,
        )
        result = _generate_recommendations([report])
        assert "QUICK SETUP" in result
        assert "OGREP_MODEL" in result
        assert "OGREP_BASE_URL" in result  # Local model should have this
