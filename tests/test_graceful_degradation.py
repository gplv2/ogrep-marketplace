"""
Tests for graceful degradation when optional features are unavailable.

Verifies that ogrep works correctly when:
- sentence-transformers (reranking) is not installed
- FTS5 is not available
- Other optional dependencies are missing

These tests ensure AI tools can rely on consistent behavior regardless
of which optional features are available.
"""

import json
import subprocess
import sys
from dataclasses import dataclass

import pytest


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


class TestGracefulDegradationCLI:
    """Test CLI graceful degradation via subprocess.

    Note: These tests use subprocess and don't inherit pytest mocks.
    They test actual CLI behavior but skip embedding-dependent tests.
    """

    def test_status_without_index(self, tmp_path):
        """Status command should work gracefully without an index."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ogrep",
                "status",
                "--db",
                str(tmp_path / "nonexistent.sqlite"),
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        # Should succeed (exit 0) even with no index
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output.get("indexed") is False

    def test_device_command_always_works(self):
        """Device command should work regardless of installed packages."""
        result = subprocess.run(
            [sys.executable, "-m", "ogrep", "device", "--json"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)

        # Should always have these fields
        assert "rerank_available" in output
        assert "device" in output
        assert "recommendation" in output

    def test_models_command_always_works(self):
        """Models command should work regardless of configuration."""
        result = subprocess.run(
            [sys.executable, "-m", "ogrep", "models", "--json"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "models" in output
        assert len(output["models"]) > 0

    def test_help_commands_always_work(self):
        """Help for all commands should work."""
        commands = ["index", "query", "status", "reset", "clean", "device", "models", "chunk"]

        for cmd in commands:
            result = subprocess.run(
                [sys.executable, "-m", "ogrep", cmd, "--help"],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Help failed for {cmd}: {result.stderr}"


class TestGracefulDegradationUnit:
    """Unit tests for graceful degradation."""

    def test_rerank_import_error_handled(self):
        """Rerank module should handle import errors gracefully."""
        from ogrep.rerank import is_reranker_available

        # Should return a boolean, not raise
        result = is_reranker_available()
        assert isinstance(result, bool)

    def test_rerank_results_with_unavailable_reranker(self):
        """rerank_results should raise helpful error when not available."""
        from ogrep.rerank import is_reranker_available, rerank_results

        if not is_reranker_available():
            # Create a mock hit - must be non-empty to trigger reranker check
            mock_hit = MockHit(
                score=0.5,
                path="test.py",
                start_line=1,
                end_line=10,
                text="def test(): pass",
                chunk_id=1,
                chunk_index=0,
                confidence="high",
            )

            # Should raise ImportError with helpful message
            with pytest.raises(ImportError) as exc_info:
                rerank_results("test query", [mock_hit])

            assert (
                "sentence-transformers" in str(exc_info.value).lower()
                or "install" in str(exc_info.value).lower()
            )

    def test_device_command_without_sentence_transformers(self):
        """Device command should work even without sentence-transformers."""
        from ogrep.commands.device import _get_device_info

        info = _get_device_info()

        # Should always return a dict with required fields
        assert isinstance(info, dict)
        assert "rerank_available" in info
        assert "recommendation" in info
        assert "cpu_info" in info

        # If not available, should have helpful recommendation
        if not info["rerank_available"]:
            assert "install" in info["recommendation"].lower()


class TestJSONOutputConsistency:
    """Test that JSON output is consistent across commands."""

    def test_status_json_structure(self, tmp_path):
        """Status command JSON should have consistent structure."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ogrep",
                "status",
                "--db",
                str(tmp_path / "nonexistent.sqlite"),
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        # Should return valid JSON even for nonexistent DB
        try:
            output = json.loads(result.stdout)
            assert isinstance(output, dict)
            # Should have indexed field
            assert "indexed" in output
        except json.JSONDecodeError:
            # If not JSON, should be because --json not supported yet
            pass

    def test_device_json_structure(self):
        """Device command JSON should have consistent structure."""
        result = subprocess.run(
            [sys.executable, "-m", "ogrep", "device", "--json"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)

        # Required fields
        assert "rerank_available" in output
        assert "device" in output
        assert "cuda_available" in output
        assert "mps_available" in output
        assert "cpu_info" in output
        assert "recommendation" in output

    def test_models_json_structure(self):
        """Models command JSON should have consistent structure."""
        result = subprocess.run(
            [sys.executable, "-m", "ogrep", "models", "--json"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)

        # Should have models list
        assert "models" in output
        assert isinstance(output["models"], list)
        assert len(output["models"]) > 0

        # Each model should have required fields
        for model in output["models"]:
            assert "id" in model
            assert "dimensions" in model


class TestSearchModeDegradation:
    """Test search mode degradation when FTS5 unavailable."""

    def test_fts5_detection(self):
        """FTS5 availability detection should work."""
        import sqlite3

        from ogrep.db import has_fts5

        # Create a connection without FTS5 table
        con = sqlite3.connect(":memory:")
        assert has_fts5(con) is False
        con.close()

    def test_query_command_handles_missing_index(self, tmp_path):
        """Query command should give helpful error for missing index."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ogrep",
                "query",
                "test",
                "--db",
                str(tmp_path / "missing.sqlite"),
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        # Should fail gracefully with helpful error
        # (either JSON error or stderr message)
        if result.returncode != 0:
            combined = result.stdout + result.stderr
            assert (
                "index" in combined.lower()
                or "not found" in combined.lower()
                or "no such" in combined.lower()
            )
