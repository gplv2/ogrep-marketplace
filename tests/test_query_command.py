"""Tests for ogrep.commands.query module."""

from __future__ import annotations

import argparse
import sqlite3
import time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from ogrep.commands.query import _check_stale_files, cmd_query
from ogrep.db import connect
from ogrep.embed import embed_texts
from ogrep.indexer import index_path


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

        # Index the repo
        db_path = temp_dir / ".ogrep" / "index.sqlite"
        index_path(root=temp_dir, db_path=db_path)

        return temp_dir, db_path

    def test_query_missing_database(self, temp_dir: Path, capsys) -> None:
        """Test query with missing database."""
        args = argparse.Namespace(
            query="test",
            top=10,
            refresh=False,
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
        lines = [l for l in captured.out.strip().split("\n") if l]
        # With top=1, we should have 2 lines (1 result with path + snippet)
        assert len(lines) <= 2

    def test_query_output_format(self, indexed_repo, capsys) -> None:
        """Test that output format is correct."""
        repo_dir, db_path = indexed_repo

        args = argparse.Namespace(
            query="database connection",
            top=5,
            refresh=False,
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
