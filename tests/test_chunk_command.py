"""Tests for ogrep.commands.chunk module."""

from __future__ import annotations

import array
import json
from pathlib import Path

import pytest

from ogrep.commands.chunk import _parse_chunk_ref, cmd_chunk
from ogrep.db import connect


class TestParseChunkRef:
    """Tests for _parse_chunk_ref function."""

    def test_raw_id(self) -> None:
        """Test parsing a raw chunk ID."""
        rel_path, chunk_index, chunk_id = _parse_chunk_ref("42")
        assert rel_path is None
        assert chunk_index is None
        assert chunk_id == 42

    def test_path_and_index(self) -> None:
        """Test parsing path:index format."""
        rel_path, chunk_index, chunk_id = _parse_chunk_ref("src/auth.py:2")
        assert rel_path == "src/auth.py"
        assert chunk_index == 2
        assert chunk_id is None

    def test_nested_path(self) -> None:
        """Test parsing deeply nested path."""
        rel_path, chunk_index, chunk_id = _parse_chunk_ref("a/b/c/file.py:10")
        assert rel_path == "a/b/c/file.py"
        assert chunk_index == 10
        assert chunk_id is None

    def test_path_only(self) -> None:
        """Test parsing path without index."""
        rel_path, chunk_index, chunk_id = _parse_chunk_ref("src/file.py")
        assert rel_path == "src/file.py"
        assert chunk_index is None
        assert chunk_id is None


class TestCmdChunk:
    """Tests for cmd_chunk command."""

    @pytest.fixture
    def indexed_db(self, temp_dir: Path) -> Path:
        """Create a database with indexed chunks."""
        db_path = temp_dir / ".ogrep" / "index.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connect(db_path).close()
        con = connect(db_path)

        # Create a test file
        test_file = temp_dir / "src" / "auth.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("# auth module\n" * 100)

        # Insert file record
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            (str(test_file), 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert multiple chunks for context testing
        fake_embedding = array.array("f", [0.1] * 256).tobytes()
        for i in range(5):
            con.execute(
                """INSERT INTO chunks
                   (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    file_id,
                    i,
                    i * 20 + 1,
                    (i + 1) * 20,
                    f"# Chunk {i}\ndef function_{i}():\n    pass",
                    f"hash{i}",
                    fake_embedding,
                    256,
                    "test-model",
                ),
            )
        con.commit()
        con.close()

        return db_path

    def test_chunk_by_path_index(self, indexed_db: Path, temp_dir: Path) -> None:
        """Test retrieving chunk by path:index format."""
        args = type(
            "Args",
            (),
            {
                "ref": "src/auth.py:2",
                "before": 0,
                "after": 0,
                "context": 0,
                "db": str(indexed_db),
                "profile": None,
                "global_cache": False,
                "repo_root": temp_dir,
            },
        )()

        import io
        import sys

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_chunk(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        assert output["requested"]["chunk_ref"] == "src/auth.py:2"
        assert output["requested"]["chunk_index"] == 2
        assert output["before"] == []
        assert output["after"] == []

    def test_chunk_by_raw_id(self, indexed_db: Path, temp_dir: Path) -> None:
        """Test retrieving chunk by raw ID."""
        # Get actual chunk ID from database
        con = connect(indexed_db)
        chunk_id = con.execute("SELECT id FROM chunks WHERE chunk_index = 1").fetchone()[0]
        con.close()

        args = type(
            "Args",
            (),
            {
                "ref": str(chunk_id),
                "before": 0,
                "after": 0,
                "context": 0,
                "db": str(indexed_db),
                "profile": None,
                "global_cache": False,
                "repo_root": temp_dir,
            },
        )()

        import io
        import sys

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_chunk(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        assert output["requested"]["chunk_id"] == chunk_id
        assert output["requested"]["chunk_index"] == 1

    def test_chunk_with_before(self, indexed_db: Path, temp_dir: Path) -> None:
        """Test retrieving chunk with preceding chunks."""
        args = type(
            "Args",
            (),
            {
                "ref": "src/auth.py:2",
                "before": 2,
                "after": 0,
                "context": 0,
                "db": str(indexed_db),
                "profile": None,
                "global_cache": False,
                "repo_root": temp_dir,
            },
        )()

        import io
        import sys

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_chunk(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        assert len(output["before"]) == 2
        # Should be in ascending order (chunk 0, chunk 1)
        assert output["before"][0]["chunk_index"] == 0
        assert output["before"][1]["chunk_index"] == 1
        assert output["after"] == []

    def test_chunk_with_after(self, indexed_db: Path, temp_dir: Path) -> None:
        """Test retrieving chunk with following chunks."""
        args = type(
            "Args",
            (),
            {
                "ref": "src/auth.py:2",
                "before": 0,
                "after": 2,
                "context": 0,
                "db": str(indexed_db),
                "profile": None,
                "global_cache": False,
                "repo_root": temp_dir,
            },
        )()

        import io
        import sys

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_chunk(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        assert output["before"] == []
        assert len(output["after"]) == 2
        # Should be in ascending order (chunk 3, chunk 4)
        assert output["after"][0]["chunk_index"] == 3
        assert output["after"][1]["chunk_index"] == 4

    def test_chunk_with_context(self, indexed_db: Path, temp_dir: Path) -> None:
        """Test --context flag (both before and after)."""
        args = type(
            "Args",
            (),
            {
                "ref": "src/auth.py:2",
                "before": 0,
                "after": 0,
                "context": 1,
                "db": str(indexed_db),
                "profile": None,
                "global_cache": False,
                "repo_root": temp_dir,
            },
        )()

        import io
        import sys

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_chunk(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        assert len(output["before"]) == 1
        assert len(output["after"]) == 1
        assert output["before"][0]["chunk_index"] == 1
        assert output["after"][0]["chunk_index"] == 3

    def test_chunk_not_found(self, indexed_db: Path, temp_dir: Path) -> None:
        """Test error when chunk doesn't exist."""
        args = type(
            "Args",
            (),
            {
                "ref": "nonexistent.py:99",
                "before": 0,
                "after": 0,
                "context": 0,
                "db": str(indexed_db),
                "profile": None,
                "global_cache": False,
                "repo_root": temp_dir,
            },
        )()

        import io
        import sys

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_chunk(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 1
        output = json.loads(captured.getvalue())
        assert "error" in output

    def test_chunk_missing_database(self, temp_dir: Path) -> None:
        """Test error when database doesn't exist."""
        args = type(
            "Args",
            (),
            {
                "ref": "src/auth.py:0",
                "before": 0,
                "after": 0,
                "context": 0,
                "db": str(temp_dir / "nonexistent.sqlite"),
                "profile": None,
                "global_cache": False,
                "repo_root": temp_dir,
            },
        )()

        import io
        import sys

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_chunk(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 1
        output = json.loads(captured.getvalue())
        assert "error" in output
        assert "not found" in output["error"]

    def test_chunk_language_detection(self, indexed_db: Path, temp_dir: Path) -> None:
        """Test that language is detected from file extension."""
        args = type(
            "Args",
            (),
            {
                "ref": "src/auth.py:0",
                "before": 0,
                "after": 0,
                "context": 0,
                "db": str(indexed_db),
                "profile": None,
                "global_cache": False,
                "repo_root": temp_dir,
            },
        )()

        import io
        import sys

        captured = io.StringIO()
        sys.stdout = captured
        try:
            result = cmd_chunk(args)
        finally:
            sys.stdout = sys.__stdout__

        assert result == 0
        output = json.loads(captured.getvalue())
        assert output["requested"]["language"] == "python"
