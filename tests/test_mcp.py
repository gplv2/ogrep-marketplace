"""Tests for the ogrep MCP server tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from ogrep.mcp.__main__ import (
    _resolve_context,
    ogrep_chunk,
    ogrep_health,
    ogrep_index,
    ogrep_query,
    ogrep_status,
)


class TestResolveContext:
    """Tests for _resolve_context helper."""

    def test_resolve_in_git_repo(self, sample_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """_resolve_context finds git root and DB path."""
        # Init a git repo so find_git_root works
        import subprocess

        subprocess.run(["git", "init"], cwd=sample_repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=sample_repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=sample_repo,
            capture_output=True,
        )

        repo_root, db_path = _resolve_context(str(sample_repo))
        assert repo_root == sample_repo
        assert db_path == sample_repo / ".ogrep" / "index.sqlite"

    def test_resolve_non_git(self, temp_dir: Path) -> None:
        """_resolve_context falls back to target dir for non-git paths."""
        repo_root, db_path = _resolve_context(str(temp_dir))
        assert repo_root == temp_dir
        assert db_path == temp_dir / ".ogrep" / "index.sqlite"


class TestOgrepStatus:
    """Tests for ogrep_status tool."""

    def test_status_no_index(self, temp_dir: Path) -> None:
        """Returns not_indexed when no DB exists."""
        result = ogrep_status(path=str(temp_dir))
        assert result["indexed"] is False
        assert result["status"] == "not_indexed"

    def test_status_with_index(self, sample_repo: Path) -> None:
        """Returns index info after indexing."""
        import subprocess

        subprocess.run(["git", "init"], cwd=sample_repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=sample_repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=sample_repo,
            capture_output=True,
        )

        # Index first
        ogrep_index(path=str(sample_repo))

        result = ogrep_status(path=str(sample_repo))
        assert result["indexed"] is True
        assert result["status"] == "indexed"
        assert result["total_files"] > 0
        assert result["chunks"] > 0
        assert result["model"] is not None


class TestOgrepIndex:
    """Tests for ogrep_index tool."""

    def test_index_directory(self, sample_repo: Path) -> None:
        """Index a sample repo and verify stats."""
        import subprocess

        subprocess.run(["git", "init"], cwd=sample_repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=sample_repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=sample_repo,
            capture_output=True,
        )

        result = ogrep_index(path=str(sample_repo))
        assert result["status"] == "ok"
        assert result["files_indexed"] > 0
        assert result["chunks_total"] > 0
        assert result["model"] is not None

    def test_index_incremental(self, sample_repo: Path) -> None:
        """Second index run reuses existing chunks."""
        import subprocess

        subprocess.run(["git", "init"], cwd=sample_repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=sample_repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=sample_repo,
            capture_output=True,
        )

        ogrep_index(path=str(sample_repo))
        result2 = ogrep_index(path=str(sample_repo))
        # Second run should skip files (already indexed, unchanged)
        assert result2["status"] == "ok"
        assert result2["files_indexed"] == 0 or result2["chunks_reused"] > 0


class TestOgrepQuery:
    """Tests for ogrep_query tool."""

    @pytest.fixture(autouse=True)
    def _indexed_repo(self, sample_repo: Path) -> Path:
        """Index the sample repo before each query test."""
        import subprocess

        subprocess.run(["git", "init"], cwd=sample_repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=sample_repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=sample_repo,
            capture_output=True,
        )

        ogrep_index(path=str(sample_repo))
        self.repo = sample_repo
        return sample_repo

    def test_query_returns_results(self) -> None:
        """Basic query returns results with expected fields."""
        result = ogrep_query(query="hello world function", path=str(self.repo))
        assert "results" in result
        assert "stats" in result
        assert result["query"] == "hello world function"
        assert len(result["results"]) > 0

        first = result["results"][0]
        assert "chunk_ref" in first
        assert "score" in first
        assert "text" in first
        assert "confidence" in first

    def test_query_summarize(self) -> None:
        """Summarize mode returns file-level aggregation."""
        result = ogrep_query(
            query="calculate sum", path=str(self.repo), summarize=True
        )
        assert result.get("summary") is True
        assert "files" in result
        assert len(result["files"]) > 0

        first_file = result["files"][0]
        assert "relative_path" in first_file
        assert "best_score" in first_file
        assert "chunks_matched" in first_file

    def test_query_with_glob(self) -> None:
        """Glob filter restricts results to matching files."""
        result = ogrep_query(
            query="function", path=str(self.repo), glob="*.py"
        )
        assert "results" in result
        # All results should be .py files
        for r in result["results"]:
            assert r["relative_path"].endswith(".py")

    def test_query_modes(self) -> None:
        """Different search modes work."""
        for mode in ("hybrid", "semantic", "fulltext"):
            result = ogrep_query(
                query="hello", path=str(self.repo), mode=mode
            )
            assert "error" not in result or "results" in result


def test_query_no_index(temp_dir: Path) -> None:
    """Query without index returns error."""
    result = ogrep_query(query="test", path=str(temp_dir))
    assert "error" in result


class TestOgrepChunk:
    """Tests for ogrep_chunk tool."""

    @pytest.fixture(autouse=True)
    def _indexed_repo(self, sample_repo: Path) -> Path:
        """Index the sample repo before each chunk test."""
        import subprocess

        subprocess.run(["git", "init"], cwd=sample_repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=sample_repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=sample_repo,
            capture_output=True,
        )

        ogrep_index(path=str(sample_repo))
        self.repo = sample_repo
        return sample_repo

    def test_chunk_by_ref(self) -> None:
        """Retrieve a chunk by path:index reference."""
        # First query to get a valid chunk_ref
        qresult = ogrep_query(query="hello", path=str(self.repo))
        assert len(qresult["results"]) > 0
        chunk_ref = qresult["results"][0]["chunk_ref"]

        result = ogrep_chunk(ref=chunk_ref, path=str(self.repo))
        assert "requested" in result
        assert "text" in result["requested"]

    def test_chunk_with_context(self) -> None:
        """Context parameter includes surrounding chunks."""
        qresult = ogrep_query(query="hello", path=str(self.repo))
        chunk_ref = qresult["results"][0]["chunk_ref"]

        result = ogrep_chunk(ref=chunk_ref, path=str(self.repo), context=1)
        assert "requested" in result
        assert "before" in result
        assert "after" in result

    def test_chunk_invalid_ref(self) -> None:
        """Invalid chunk reference returns error."""
        result = ogrep_chunk(ref="nonexistent/file.py:999", path=str(self.repo))
        assert "error" in result

    def test_chunk_no_index(self, temp_dir: Path) -> None:
        """Chunk without index returns error."""
        result = ogrep_chunk(ref="test.py:0", path=str(temp_dir))
        assert "error" in result


class TestOgrepHealth:
    """Tests for ogrep_health tool."""

    def test_health_no_index(self, temp_dir: Path) -> None:
        """Returns not_indexed when no DB exists."""
        result = ogrep_health(path=str(temp_dir))
        assert result["exists"] is False

    def test_health_with_index(self, sample_repo: Path) -> None:
        """Returns diagnostics after indexing."""
        import subprocess

        subprocess.run(["git", "init"], cwd=sample_repo, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=sample_repo,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=sample_repo,
            capture_output=True,
        )

        ogrep_index(path=str(sample_repo))

        result = ogrep_health(path=str(sample_repo))
        assert result["exists"] is True
        assert result["quick_check"] == "ok"
        assert "tables" in result
        assert "sqlite" in result
        assert result["model"] is not None
