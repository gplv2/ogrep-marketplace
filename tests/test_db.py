"""Database tests."""

from __future__ import annotations

from pathlib import Path

from ogrep.db import connect


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
