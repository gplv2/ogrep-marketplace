"""Database tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ogrep.db import DatabaseError, connect


def test_db_creation(temp_dir: Path) -> None:
    """Test that database is created with correct schema."""
    db_path = temp_dir / "test.sqlite"
    con = connect(db_path)

    # Check that tables exist
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]

    assert "files" in tables
    assert "chunks" in tables

    con.close()


def test_db_schema_files(temp_dir: Path) -> None:
    """Test files table schema."""
    db_path = temp_dir / "test.sqlite"
    con = connect(db_path)

    cur = con.cursor()
    cur.execute("PRAGMA table_info(files)")
    columns = {row[1]: row[2] for row in cur.fetchall()}

    assert "id" in columns
    assert "path" in columns
    assert "mtime_ns" in columns
    assert "size" in columns
    assert "sha256" in columns

    con.close()


def test_db_schema_chunks(temp_dir: Path) -> None:
    """Test chunks table schema."""
    db_path = temp_dir / "test.sqlite"
    con = connect(db_path)

    cur = con.cursor()
    cur.execute("PRAGMA table_info(chunks)")
    columns = {row[1]: row[2] for row in cur.fetchall()}

    assert "id" in columns
    assert "file_id" in columns
    assert "chunk_index" in columns
    assert "start_line" in columns
    assert "end_line" in columns
    assert "text" in columns
    assert "embedding" in columns
    assert "dim" in columns
    assert "model" in columns

    con.close()


def test_db_wal_mode(temp_dir: Path) -> None:
    """Test that WAL mode is enabled."""
    db_path = temp_dir / "test.sqlite"
    con = connect(db_path)

    cur = con.cursor()
    cur.execute("PRAGMA journal_mode")
    mode = cur.fetchone()[0]

    assert mode.lower() == "wal"

    con.close()


def test_db_parent_directory_creation(temp_dir: Path) -> None:
    """Test that parent directories are created automatically."""
    db_path = temp_dir / "nested" / "dir" / "test.sqlite"
    con = connect(db_path)

    assert db_path.exists()

    con.close()


class TestDatabaseErrorHandling:
    """Tests for database error handling and helpful error messages."""

    def test_error_message_for_permission_denied(self, temp_dir: Path) -> None:
        """Test that permission errors produce helpful messages."""
        # Create a read-only directory
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        os.chmod(readonly_dir, 0o444)

        db_path = readonly_dir / "subdir" / "test.sqlite"

        try:
            with pytest.raises(DatabaseError) as exc_info:
                connect(db_path)

            assert "Cannot create database directory" in str(exc_info.value)
            assert "write permissions" in str(exc_info.value)
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, 0o755)

    def test_error_message_for_corrupted_database(self, temp_dir: Path) -> None:
        """Test that corrupted database files produce helpful messages."""
        db_path = temp_dir / "corrupted.sqlite"

        # Create a file with invalid content (not a valid SQLite database)
        db_path.write_text("this is not a valid sqlite database")

        with pytest.raises(DatabaseError) as exc_info:
            connect(db_path)

        error_msg = str(exc_info.value)
        # Should suggest removing and reindexing
        assert (
            "corrupted" in error_msg.lower()
            or "malformed" in error_msg.lower()
            or "not a database" in error_msg.lower()
        )

    def test_database_error_exception_exists(self) -> None:
        """DatabaseError should be a proper exception class."""
        assert issubclass(DatabaseError, Exception)

        # Should be raisable with a message
        try:
            raise DatabaseError("Test error message")
        except DatabaseError as e:
            assert "Test error message" in str(e)

    def test_successful_connect_no_error(self, temp_dir: Path) -> None:
        """Normal operation should not raise DatabaseError."""
        db_path = temp_dir / "normal.sqlite"

        # Should not raise
        con = connect(db_path)
        assert con is not None

        # Verify it's a working connection
        con.execute("SELECT 1").fetchone()
        con.close()
