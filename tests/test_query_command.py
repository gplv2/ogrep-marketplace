"""Tests for ogrep.commands.query module."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

import pytest

from ogrep.commands._common import detect_language
from ogrep.commands.query import (
    _check_stale_files,
    _format_json_result,
    _format_text_output,
    _get_index_info,
    cmd_query,
)
from ogrep.db import connect
from ogrep.indexer import index_path
from ogrep.search import Hit


class TestCheckStaleFiles:
    """Tests for _check_stale_files function."""

    def test_no_stale_files(self, temp_dir: Path) -> None:
        """Test when all files are up to date."""
        db_path = temp_dir / "index.sqlite"

        # Create a file
        test_file = temp_dir / "test.py"
        test_file.write_text("print('hello')")
        stat = test_file.stat()

        # Create database with matching metadata
        connect(db_path).close()
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            (str(test_file), stat.st_mtime_ns, stat.st_size, "abc123"),
        )
        con.commit()
        con.close()

        stale = _check_stale_files(db_path, temp_dir)
        assert stale == []

    def test_modified_file_detected(self, temp_dir: Path) -> None:
        """Test that modified files are detected."""
        db_path = temp_dir / "index.sqlite"

        # Create a file
        test_file = temp_dir / "test.py"
        test_file.write_text("print('hello')")

        # Create database with old metadata
        connect(db_path).close()
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            (str(test_file), 0, 50, "abc123"),  # Old mtime and different size
        )
        con.commit()
        con.close()

        stale = _check_stale_files(db_path, temp_dir)
        assert len(stale) == 1
        assert stale[0] == test_file

    def test_deleted_file_detected(self, temp_dir: Path) -> None:
        """Test that deleted files are detected."""
        db_path = temp_dir / "index.sqlite"

        # Reference a non-existent file
        missing_file = temp_dir / "deleted.py"

        # Create database with reference to missing file
        connect(db_path).close()
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            (str(missing_file), 12345, 100, "abc123"),
        )
        con.commit()
        con.close()

        stale = _check_stale_files(db_path, temp_dir)
        assert len(stale) == 1
        assert stale[0] == missing_file

    def test_multiple_stale_files(self, temp_dir: Path) -> None:
        """Test detecting multiple stale files."""
        db_path = temp_dir / "index.sqlite"

        # Create one file that exists but is modified
        modified_file = temp_dir / "modified.py"
        modified_file.write_text("modified content")

        # Reference one deleted file
        deleted_file = temp_dir / "deleted.py"

        connect(db_path).close()
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            (str(modified_file), 0, 1, "old"),  # Wrong metadata
        )
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            (str(deleted_file), 12345, 100, "abc"),
        )
        con.commit()
        con.close()

        stale = _check_stale_files(db_path, temp_dir)
        assert len(stale) == 2

    def test_empty_database(self, temp_dir: Path) -> None:
        """Test with empty database."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()

        stale = _check_stale_files(db_path, temp_dir)
        assert stale == []


class TestCmdQuery:
    """Tests for cmd_query function."""

    @pytest.fixture
    def indexed_repo(self, temp_dir: Path) -> tuple[Path, Path]:
        """Create a temporary repo with indexed files."""
        # Create source files
        src_dir = temp_dir / "src"
        src_dir.mkdir()
        (src_dir / "auth.py").write_text(
            '''"""Authentication module."""

def authenticate_user(username: str, password: str) -> bool:
    """Authenticate a user with username and password."""
    return check_credentials(username, password)

def check_credentials(user: str, pwd: str) -> bool:
    """Verify credentials against database."""
    return True
'''
        )
        (src_dir / "db.py").write_text(
            '''"""Database module."""

def connect_database(host: str, port: int):
    """Connect to the database server."""
    return Connection(host, port)

def execute_query(sql: str):
    """Execute a SQL query."""
    pass
'''
        )

        # Index the repo (explicitly use text-embedding-3-small for test consistency)
        db_path = temp_dir / ".ogrep" / "index.sqlite"
        index_path(root=temp_dir, db_path=db_path, model="text-embedding-3-small")

        return temp_dir, db_path

    def test_query_missing_database(self, temp_dir: Path, capsys) -> None:
        """Test query with missing database."""
        args = argparse.Namespace(
            query="test",
            top=10,
            refresh=False,
            json=False,
            db=None,
            profile=None,
            global_cache=False,
            repo_root=temp_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Database not found" in captured.err
        assert "ogrep index" in captured.err

    def test_query_returns_results(self, indexed_repo, capsys) -> None:
        """Test that query returns matching results."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="user authentication",
            top=5,
            refresh=False,
            json=False,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "auth.py" in captured.out
        assert "score=" in captured.out

    def test_query_with_top_limit(self, indexed_repo, capsys) -> None:
        """Test that top limit is respected in output."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="function",
            top=1,
            refresh=False,
            json=False,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0

        captured = capsys.readouterr()
        # Count result lines (each result has path line + snippet line)
        lines = [line for line in captured.out.strip().split("\n") if line]
        # With top=1, we should have 2 lines (1 result with path + snippet)
        assert len(lines) <= 2

    def test_query_output_format(self, indexed_repo, capsys) -> None:
        """Test that output format is correct."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="database connection",
            top=5,
            refresh=False,
            json=False,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0

        captured = capsys.readouterr()
        # Check format: path:start-end  score=X.XXXX
        lines = captured.out.strip().split("\n")
        # First line should have the format with score
        assert "score=" in lines[0]
        assert ":" in lines[0]

    def test_query_with_refresh_flag(self, indexed_repo, capsys) -> None:
        """Test query with --refresh flag when no files changed."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="authentication",
            top=5,
            refresh=True,
            json=False,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)

        assert result == 0
        captured = capsys.readouterr()
        # Should not show refresh message when nothing changed
        assert "Refreshing" not in captured.err

    def test_query_refresh_with_modified_file(self, indexed_repo, capsys) -> None:
        """Test query with --refresh detects and reindexes modified files."""
        repo_dir, db_path = indexed_repo

        # Wait a moment then modify a file
        time.sleep(0.01)
        (repo_dir / "src" / "auth.py").write_text(
            '''"""Updated authentication."""

def login(user: str, pwd: str) -> bool:
    """New login function."""
    return True
'''
        )

        args = argparse.Namespace(
            query="login",
            top=5,
            refresh=True,
            json=False,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)

        assert result == 0
        captured = capsys.readouterr()
        # Should show refresh activity
        assert "Refreshing" in captured.err or "Updated" in captured.err


class TestCmdQueryEdgeCases:
    """Edge case tests for cmd_query."""

    def test_query_empty_index(self, temp_dir: Path, capsys) -> None:
        """Test query against empty but valid index."""
        db_path = temp_dir / ".ogrep" / "index.sqlite"
        db_path.parent.mkdir(parents=True)
        connect(db_path).close()

        args = argparse.Namespace(
            query="anything",
            top=10,
            refresh=False,
            json=False,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=temp_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0  # Should succeed but return no results

        captured = capsys.readouterr()
        assert captured.out.strip() == ""  # No results

    def test_query_special_characters(self, temp_dir: Path) -> None:
        """Test query with special characters."""
        db_path = temp_dir / ".ogrep" / "index.sqlite"
        db_path.parent.mkdir(parents=True)
        connect(db_path).close()

        args = argparse.Namespace(
            query="def __init__(self):",
            top=10,
            refresh=False,
            json=False,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=temp_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        # Should not raise
        result = cmd_query(args)
        assert result == 0


class TestDetectLanguage:
    """Tests for detect_language utility function."""

    def test_python_extensions(self) -> None:
        """Test Python file extension detection."""
        assert detect_language("/path/to/file.py") == "python"
        assert detect_language("test.pyi") == "python"
        assert detect_language("cython.pyx") == "python"

    def test_javascript_typescript(self) -> None:
        """Test JS/TS file extension detection."""
        assert detect_language("app.js") == "javascript"
        assert detect_language("component.jsx") == "javascript"
        assert detect_language("service.ts") == "typescript"
        assert detect_language("component.tsx") == "typescript"

    def test_systems_languages(self) -> None:
        """Test systems language detection."""
        assert detect_language("main.c") == "c"
        assert detect_language("header.h") == "c"
        assert detect_language("class.cpp") == "cpp"
        assert detect_language("lib.rs") == "rust"
        assert detect_language("server.go") == "go"

    def test_unknown_extension(self) -> None:
        """Test unknown file extension returns None."""
        assert detect_language("Makefile") is None
        assert detect_language("README") is None
        assert detect_language(".gitignore") is None

    def test_case_sensitivity(self) -> None:
        """Test case handling for extensions."""
        # .R is uppercase for R language
        assert detect_language("analysis.R") == "r"
        assert detect_language("script.r") == "r"


class TestCmdQueryJson:
    """Tests for cmd_query with --json flag."""

    @pytest.fixture
    def indexed_repo(self, temp_dir: Path) -> tuple[Path, Path]:
        """Create a temporary repo with indexed files."""
        src_dir = temp_dir / "src"
        src_dir.mkdir()
        (src_dir / "auth.py").write_text(
            '''"""Authentication module."""

def authenticate_user(username: str, password: str) -> bool:
    """Authenticate a user with username and password."""
    return check_credentials(username, password)

def check_credentials(user: str, pwd: str) -> bool:
    """Verify credentials against database."""
    return True
'''
        )
        (src_dir / "server.ts").write_text(
            """/**
 * Server module for handling HTTP requests.
 */
export function startServer(port: number): void {
    console.log(`Starting server on port ${port}`);
}

export function handleRequest(req: Request): Response {
    return new Response("OK");
}
"""
        )

        # Index the repo (explicitly use text-embedding-3-small for test consistency)
        db_path = temp_dir / ".ogrep" / "index.sqlite"
        index_path(root=temp_dir, db_path=db_path, model="text-embedding-3-small")

        return temp_dir, db_path

    def test_json_output_structure(self, indexed_repo, capsys) -> None:
        """Test that JSON output has correct structure."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="user authentication",
            top=5,
            refresh=False,
            json=True,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # Check top-level structure
        assert "query" in output
        assert "results" in output
        assert "stats" in output
        assert output["query"] == "user authentication"

    def test_json_result_fields(self, indexed_repo, capsys) -> None:
        """Test that each result has all required fields."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="authenticate",
            top=5,
            refresh=False,
            json=True,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert len(output["results"]) > 0
        first_result = output["results"][0]

        # Check all required fields
        assert "rank" in first_result
        assert "path" in first_result
        assert "relative_path" in first_result
        assert "start_line" in first_result
        assert "end_line" in first_result
        assert "score" in first_result
        assert "confidence" in first_result
        assert "language" in first_result
        assert "text" in first_result

        # Check types
        assert isinstance(first_result["rank"], int)
        assert isinstance(first_result["start_line"], int)
        assert isinstance(first_result["end_line"], int)
        assert isinstance(first_result["score"], float)
        assert isinstance(first_result["text"], str)
        assert first_result["confidence"] in ("high", "medium", "low", "very_low")

    def test_json_language_detection(self, indexed_repo, capsys) -> None:
        """Test that language is correctly detected from file extension."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="server http request",
            top=5,
            refresh=False,
            json=True,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # Find result for .ts file
        ts_results = [r for r in output["results"] if r["path"].endswith(".ts")]
        if ts_results:
            assert ts_results[0]["language"] == "typescript"

        # Find result for .py file
        py_results = [r for r in output["results"] if r["path"].endswith(".py")]
        if py_results:
            assert py_results[0]["language"] == "python"

    def test_json_relative_path(self, indexed_repo, capsys) -> None:
        """Test that relative_path is correctly calculated."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="authenticate",
            top=5,
            refresh=False,
            json=True,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        for r in output["results"]:
            # relative_path should not start with /
            assert not r["relative_path"].startswith("/")
            # absolute path should end with relative path
            assert r["path"].endswith(r["relative_path"])

    def test_json_stats_fields(self, indexed_repo, capsys) -> None:
        """Test that stats contain expected fields."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="function",
            top=5,
            refresh=False,
            json=True,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        stats = output["stats"]
        assert "total_results" in stats
        assert "total_chunks" in stats
        assert "search_time_ms" in stats
        assert "index_model" in stats
        assert "index_dimensions" in stats
        assert "refreshed_files" in stats
        assert "confidence_summary" in stats

        # Check types
        assert isinstance(stats["total_results"], int)
        assert isinstance(stats["total_chunks"], int)
        assert isinstance(stats["search_time_ms"], int)
        assert stats["search_time_ms"] >= 0

        # Check confidence_summary structure
        conf_summary = stats["confidence_summary"]
        assert "high" in conf_summary
        assert "medium" in conf_summary
        assert "low" in conf_summary
        assert "very_low" in conf_summary

    def test_json_full_text_not_truncated(self, indexed_repo, capsys) -> None:
        """Test that JSON output includes full text, not truncated."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="authenticate",
            top=5,
            refresh=False,
            json=True,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # JSON output should have full text with actual newlines
        for r in output["results"]:
            # Text should contain newlines (not escaped \\n)
            if len(r["text"]) > 100:
                assert "\n" in r["text"]

    def test_json_missing_database_error(self, temp_dir: Path, capsys) -> None:
        """Test JSON error output when database is missing."""
        args = argparse.Namespace(
            query="test",
            top=10,
            refresh=False,
            json=True,
            db=None,
            profile=None,
            global_cache=False,
            repo_root=temp_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 1

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "error" in output
        assert "Database not found" in output["error"]

    def test_json_rank_ordering(self, indexed_repo, capsys) -> None:
        """Test that results are ranked correctly starting from 1."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="function",
            top=5,
            refresh=False,
            json=True,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # Check ranks are sequential starting from 1
        for i, r in enumerate(output["results"]):
            assert r["rank"] == i + 1

        # Check scores are in descending order
        scores = [r["score"] for r in output["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_json_chunk_ref(self, indexed_repo, capsys) -> None:
        """Test that chunk_ref and chunk_id are included in results."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="authenticate",
            top=5,
            refresh=False,
            json=True,
            db=db_path,
            profile=None,
            global_cache=False,
            repo_root=repo_dir,
            model="text-embedding-3-small",
            dimensions=None,
        )

        result = cmd_query(args)
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert len(output["results"]) > 0
        first_result = output["results"][0]

        # Check chunk_ref and chunk_id are present
        assert "chunk_ref" in first_result
        assert "chunk_id" in first_result

        # chunk_ref format: relative_path:chunk_index
        chunk_ref = first_result["chunk_ref"]
        assert ":" in chunk_ref
        parts = chunk_ref.rsplit(":", 1)
        assert len(parts) == 2
        assert parts[1].isdigit()  # chunk_index should be a number

        # chunk_id should be a positive integer
        assert isinstance(first_result["chunk_id"], int)
        assert first_result["chunk_id"] > 0


class TestGetIndexInfo:
    """Tests for _get_index_info helper function."""

    def test_returns_model_and_dim_from_populated_index(self, temp_dir: Path) -> None:
        """Test that function returns model and dimensions from index."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()
        con = sqlite3.connect(str(db_path))
        # Insert a chunk with model info
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test.py", 123, 100, "abc"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute(
            "INSERT INTO chunks (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, model, dim) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (file_id, 0, 1, 10, "test code", "sha", b"\x00" * 12, "nomic-embed-text-v1.5", 768),
        )
        con.commit()
        con.close()

        model, dim = _get_index_info(db_path)
        assert model == "nomic-embed-text-v1.5"
        assert dim == 768

    def test_returns_none_for_empty_index(self, temp_dir: Path) -> None:
        """Test that function returns None for empty index."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()

        result = _get_index_info(db_path)
        assert result is None


class TestFormatJsonResult:
    """Tests for _format_json_result helper function."""

    def test_formats_hit_correctly(self, temp_dir: Path) -> None:
        """Test that hit is formatted into correct JSON structure."""
        hit = Hit(
            score=0.8765,
            path=str(temp_dir / "src" / "auth.py"),
            start_line=10,
            end_line=25,
            text="def authenticate():\n    pass",
            chunk_id=42,
            chunk_index=2,
            confidence="high",
        )

        result = _format_json_result(hit, repo_root=temp_dir, rank=1)

        assert result["rank"] == 1
        assert result["chunk_id"] == 42
        assert result["chunk_ref"] == "src/auth.py:2"
        assert result["path"] == str(temp_dir / "src" / "auth.py")
        assert result["relative_path"] == "src/auth.py"
        assert result["start_line"] == 10
        assert result["end_line"] == 25
        assert result["score"] == 0.8765
        assert result["confidence"] == "high"
        assert result["language"] == "python"
        assert result["text"] == "def authenticate():\n    pass"

    def test_handles_path_outside_repo_root(self) -> None:
        """Test graceful fallback when path is outside repo root."""
        hit = Hit(
            score=0.5,
            path="/other/location/file.py",
            start_line=1,
            end_line=5,
            text="code",
            chunk_id=1,
            chunk_index=0,
            confidence="low",
        )

        result = _format_json_result(hit, repo_root=Path("/home/user/project"), rank=1)

        # Should fall back to absolute path
        assert result["relative_path"] == "/other/location/file.py"


class TestFormatTextOutput:
    """Tests for _format_text_output helper function."""

    def test_formats_single_hit(self, capsys) -> None:
        """Test text output formatting for a single hit."""
        hits = [
            Hit(
                score=0.9123,
                path="/project/src/main.py",
                start_line=15,
                end_line=30,
                text="def main():\n    print('hello')\n    return 0",
                chunk_id=1,
                chunk_index=0,
                confidence="high",
            )
        ]

        _format_text_output(hits)

        captured = capsys.readouterr()
        assert "/project/src/main.py:15-30" in captured.out
        assert "score=0.9123" in captured.out
        assert "(high)" in captured.out
        # Snippet should be on second line, newlines escaped
        assert "def main():" in captured.out
        assert "\\n" in captured.out  # newlines should be escaped in text output

    def test_formats_multiple_hits(self, capsys) -> None:
        """Test text output formatting for multiple hits."""
        hits = [
            Hit(
                score=0.9,
                path="/a.py",
                start_line=1,
                end_line=10,
                text="first",
                chunk_id=1,
                chunk_index=0,
                confidence="high",
            ),
            Hit(
                score=0.7,
                path="/b.py",
                start_line=5,
                end_line=15,
                text="second",
                chunk_id=2,
                chunk_index=0,
                confidence="medium",
            ),
        ]

        _format_text_output(hits)

        captured = capsys.readouterr()
        assert "/a.py:1-10" in captured.out
        assert "/b.py:5-15" in captured.out
        assert "first" in captured.out
        assert "second" in captured.out

    def test_truncates_long_snippets(self, capsys) -> None:
        """Test that long snippets are truncated to 240 chars."""
        long_text = "x" * 500
        hits = [
            Hit(
                score=0.5,
                path="/test.py",
                start_line=1,
                end_line=10,
                text=long_text,
                chunk_id=1,
                chunk_index=0,
                confidence="medium",
            ),
        ]

        _format_text_output(hits)

        captured = capsys.readouterr()
        # Snippet line should be truncated
        snippet_line = [line for line in captured.out.split("\n") if line.strip().startswith("x")][
            0
        ]
        assert len(snippet_line.strip()) <= 242  # "  " prefix + 240 chars
