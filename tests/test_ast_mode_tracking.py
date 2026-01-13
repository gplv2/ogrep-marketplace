"""Tests for AST mode tracking in index metadata."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from ogrep.db import connect, get_metadata, set_metadata, get_all_metadata
from ogrep.indexer import index_path


class TestMetadataFunctions:
    """Test metadata storage functions."""

    def test_set_and_get_metadata(self, tmp_path: Path) -> None:
        """Test basic metadata set/get."""
        db_path = tmp_path / "test.db"
        con = connect(db_path)

        set_metadata(con, "test_key", "test_value")
        result = get_metadata(con, "test_key")

        assert result == "test_value"
        con.close()

    def test_get_metadata_default(self, tmp_path: Path) -> None:
        """Test default value when key not found."""
        db_path = tmp_path / "test.db"
        con = connect(db_path)

        result = get_metadata(con, "nonexistent", "default_val")

        assert result == "default_val"
        con.close()

    def test_get_metadata_none_default(self, tmp_path: Path) -> None:
        """Test None returned when no default."""
        db_path = tmp_path / "test.db"
        con = connect(db_path)

        result = get_metadata(con, "nonexistent")

        assert result is None
        con.close()

    def test_set_metadata_upsert(self, tmp_path: Path) -> None:
        """Test that set_metadata updates existing values."""
        db_path = tmp_path / "test.db"
        con = connect(db_path)

        set_metadata(con, "key", "value1")
        set_metadata(con, "key", "value2")
        result = get_metadata(con, "key")

        assert result == "value2"
        con.close()

    def test_get_all_metadata(self, tmp_path: Path) -> None:
        """Test retrieving all metadata."""
        db_path = tmp_path / "test.db"
        con = connect(db_path)

        set_metadata(con, "key1", "value1")
        set_metadata(con, "key2", "value2")
        result = get_all_metadata(con)

        assert result == {"key1": "value1", "key2": "value2"}
        con.close()


class TestAstModeTracking:
    """Test AST mode tracking during indexing."""

    @pytest.fixture
    def sample_code(self, tmp_path: Path) -> Path:
        """Create a simple Python file for testing."""
        code_file = tmp_path / "sample.py"
        code_file.write_text("""
def hello():
    print("Hello!")

def goodbye():
    print("Goodbye!")
""")
        return tmp_path

    def test_index_without_ast_stores_false(self, sample_code: Path) -> None:
        """Index without --ast should store ast_mode=false."""
        db_path = sample_code / ".ogrep" / "index.sqlite"

        index_path(
            root=sample_code,
            db_path=db_path,
            ast=False,
        )

        con = sqlite3.connect(str(db_path))
        ast_mode = con.execute(
            "SELECT value FROM index_metadata WHERE key = 'ast_mode'"
        ).fetchone()
        con.close()

        assert ast_mode is not None
        assert ast_mode[0] == "false"

    def test_index_with_ast_stores_true(self, sample_code: Path) -> None:
        """Index with --ast should store ast_mode=true (if tree-sitter available)."""
        db_path = sample_code / ".ogrep" / "index.sqlite"

        # Check if tree-sitter is available
        try:
            from ogrep.ast_chunking import is_ast_available
            ast_available = is_ast_available()
        except ImportError:
            ast_available = False

        index_path(
            root=sample_code,
            db_path=db_path,
            ast=True,
        )

        con = sqlite3.connect(str(db_path))
        ast_mode = con.execute(
            "SELECT value FROM index_metadata WHERE key = 'ast_mode'"
        ).fetchone()
        con.close()

        assert ast_mode is not None
        # If tree-sitter is available, ast_mode should be true
        # If not, it falls back to line-based and stores false
        expected = "true" if ast_available else "false"
        assert ast_mode[0] == expected


class TestStatusCommandAstMode:
    """Test status command shows AST mode."""

    @pytest.fixture
    def indexed_repo(self, tmp_path: Path) -> Path:
        """Create an indexed repository."""
        code_file = tmp_path / "test.py"
        code_file.write_text("def test(): pass")

        db_path = tmp_path / ".ogrep" / "index.sqlite"
        index_path(root=tmp_path, db_path=db_path, ast=False)

        return tmp_path

    def test_status_shows_ast_mode(self, indexed_repo: Path) -> None:
        """Status command should show ast_mode in JSON output."""
        from ogrep.commands.status import cmd_status
        import io
        import sys

        db_path = indexed_repo / ".ogrep" / "index.sqlite"

        args = type(
            "Args",
            (),
            {
                "db": str(db_path),
                "profile": None,
                "global_cache": False,
                "repo_root": indexed_repo,
                "json": True,
            },
        )()

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_status(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        assert "ast_mode" in output
        assert output["ast_mode"] is False


class TestOldDatabaseWithoutMetadata:
    """Test handling of old databases without index_metadata table."""

    @pytest.fixture
    def old_database(self, tmp_path: Path) -> Path:
        """Create a database without the index_metadata table (simulating old format)."""
        db_path = tmp_path / ".ogrep" / "index.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create old-style database without index_metadata table
        con = sqlite3.connect(str(db_path))
        con.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS files (
              id INTEGER PRIMARY KEY,
              path TEXT NOT NULL UNIQUE,
              mtime_ns INTEGER NOT NULL,
              size INTEGER NOT NULL,
              sha256 TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chunks (
              id INTEGER PRIMARY KEY,
              file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
              chunk_index INTEGER NOT NULL,
              start_line INTEGER NOT NULL,
              end_line INTEGER NOT NULL,
              text TEXT NOT NULL,
              text_sha256 TEXT NOT NULL,
              embedding BLOB NOT NULL,
              dim INTEGER NOT NULL,
              model TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              UNIQUE(file_id, chunk_index)
            );
        """)

        # Insert a dummy file and chunk
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            (str(tmp_path / "test.py"), 0, 10, "abc123"),
        )
        # Create a dummy embedding (just zeros)
        # text-embedding-3-small defaults to 256D in current config
        import array
        dummy_embedding = array.array("f", [0.0] * 256).tobytes()
        con.execute(
            """INSERT INTO chunks (file_id, chunk_index, start_line, end_line,
               text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (1, 0, 1, 5, "def test(): pass", "sha256", dummy_embedding, 256, "text-embedding-3-small"),
        )
        con.commit()
        con.close()

        return tmp_path

    def test_status_handles_old_database(self, old_database: Path) -> None:
        """Status command should work with old databases without metadata table."""
        from ogrep.commands.status import cmd_status
        import io
        import sys

        db_path = old_database / ".ogrep" / "index.sqlite"

        args = type(
            "Args",
            (),
            {
                "db": str(db_path),
                "profile": None,
                "global_cache": False,
                "repo_root": old_database,
                "json": True,
            },
        )()

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_status(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        # Old databases won't have ast_mode
        assert "ast_mode" not in output

    def test_query_handles_old_database(self, old_database: Path) -> None:
        """Query command should work with old databases and not show AST hint."""
        from ogrep.commands.query import cmd_query
        import io
        import sys

        db_path = old_database / ".ogrep" / "index.sqlite"

        args = type(
            "Args",
            (),
            {
                "query": "test function",
                "top": 5,
                "mode": None,
                "refresh": False,
                "rerank": False,
                "rerank_top": None,
                "json": True,
                "db": str(db_path),
                "profile": None,
                "global_cache": False,
                "repo_root": old_database,
                "model": "text-embedding-3-small",
                "dimensions": 256,  # Match the dummy embedding dimensions
            },
        )()

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_query(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        # Old databases won't have ast_mode in stats
        assert "ast_mode" not in output.get("stats", {})
        # And no hint either (we can't tell if it was AST or not)
        assert "hint" not in output


class TestQueryCommandAstHint:
    """Test query command shows hint for non-AST indexes."""

    @pytest.fixture
    def non_ast_index(self, tmp_path: Path) -> Path:
        """Create a non-AST indexed repository."""
        code_file = tmp_path / "test.py"
        code_file.write_text("def authenticate(): pass")

        db_path = tmp_path / ".ogrep" / "index.sqlite"
        index_path(root=tmp_path, db_path=db_path, ast=False)

        return tmp_path

    @pytest.fixture
    def ast_index(self, tmp_path: Path) -> Path:
        """Create an AST indexed repository."""
        code_file = tmp_path / "test.py"
        code_file.write_text("def authenticate(): pass")

        db_path = tmp_path / ".ogrep" / "index.sqlite"
        index_path(root=tmp_path, db_path=db_path, ast=True)

        return tmp_path

    def test_query_shows_hint_for_non_ast(self, non_ast_index: Path) -> None:
        """Query on non-AST index should show hint."""
        from ogrep.commands.query import cmd_query
        import io
        import sys

        db_path = non_ast_index / ".ogrep" / "index.sqlite"

        args = type(
            "Args",
            (),
            {
                "query": "authentication",
                "top": 5,
                "mode": None,
                "refresh": False,
                "rerank": False,
                "rerank_top": None,
                "json": True,
                "db": str(db_path),
                "profile": None,
                "global_cache": False,
                "repo_root": non_ast_index,
                "model": None,
                "dimensions": None,
            },
        )()

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_query(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        assert output["stats"]["ast_mode"] is False
        assert "hint" in output
        assert "reindex" in output["hint"].lower()
        assert "--ast" in output["hint"]

    def test_query_no_hint_for_ast_index(self, ast_index: Path) -> None:
        """Query on AST index should not show hint."""
        from ogrep.commands.query import cmd_query
        import io
        import sys

        # Check if tree-sitter is available
        try:
            from ogrep.ast_chunking import is_ast_available
            if not is_ast_available():
                pytest.skip("tree-sitter not available")
        except ImportError:
            pytest.skip("tree-sitter not available")

        db_path = ast_index / ".ogrep" / "index.sqlite"

        args = type(
            "Args",
            (),
            {
                "query": "authentication",
                "top": 5,
                "mode": None,
                "refresh": False,
                "rerank": False,
                "rerank_top": None,
                "json": True,
                "db": str(db_path),
                "profile": None,
                "global_cache": False,
                "repo_root": ast_index,
                "model": None,
                "dimensions": None,
            },
        )()

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_query(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        assert output["stats"]["ast_mode"] is True
        assert "hint" not in output
