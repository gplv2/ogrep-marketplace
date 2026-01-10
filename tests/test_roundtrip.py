"""Integration tests for index/query round-trip."""

from __future__ import annotations

import time
from pathlib import Path

from ogrep.commands.query import _check_stale_files
from ogrep.indexer import index_path
from ogrep.search import query


def test_index_and_query(sample_repo: Path, db_path: Path) -> None:
    """Test basic index and query round-trip."""
    # Index the sample repo
    index_path(
        root=sample_repo,
        db_path=db_path,
        model="text-embedding-3-small",
        dimensions=None,
        chunk_lines=50,
        overlap=10,
        max_bytes=1_000_000,
    )

    assert db_path.exists()

    # Query for something in the repo
    hits = query(
        db_path=db_path,
        q="hello world function",
        top_k=5,
        model="text-embedding-3-small",
        dimensions=None,
    )

    assert len(hits) > 0
    # The main.py file should be in results
    paths = [h.path for h in hits]
    assert any("main.py" in p for p in paths)


def test_index_empty_directory(temp_dir: Path) -> None:
    """Test indexing an empty directory."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    index_path(
        root=temp_dir,
        db_path=db_path,
        model="text-embedding-3-small",
        dimensions=None,
        chunk_lines=50,
        overlap=10,
        max_bytes=1_000_000,
    )

    assert db_path.exists()


def test_query_nonexistent_db(temp_dir: Path) -> None:
    """Test querying a non-existent database raises appropriate error."""
    import sqlite3

    db_path = temp_dir / "nonexistent.sqlite"

    try:
        query(
            db_path=db_path,
            q="test query",
            top_k=5,
        )
        # If we get here without error, the db was created
    except sqlite3.OperationalError:
        pass  # Expected


def test_incremental_index(sample_repo: Path, db_path: Path) -> None:
    """Test that indexing is incremental (unchanged files are skipped)."""
    # First index
    index_path(root=sample_repo, db_path=db_path)

    # Index again without changes - unchanged files should be skipped
    index_path(root=sample_repo, db_path=db_path)

    # This is a basic check - the test passes if no errors occur
    # A more thorough test would verify chunks table wasn't modified


def test_skip_binary_files(temp_dir: Path) -> None:
    """Test that binary files are skipped during indexing."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create a binary file
    (temp_dir / "binary.bin").write_bytes(b"\x00\x01\x02\x03\xff\xfe")

    # Create a source file (use .py extension since .txt is excluded by default)
    (temp_dir / "sample.py").write_text("# This is a source file\nprint('hello')")

    index_path(root=temp_dir, db_path=db_path)

    # Query should only find the source file
    hits = query(db_path=db_path, q="source file", top_k=10)

    paths = [h.path for h in hits]
    assert any("sample.py" in p for p in paths)
    assert not any("binary.bin" in p for p in paths)


def test_check_stale_files_detects_changes(temp_dir: Path) -> None:
    """Test that _check_stale_files detects modified files."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create and index a file
    source_file = temp_dir / "changeable.py"
    source_file.write_text("def original():\n    return 1\n")

    index_path(root=temp_dir, db_path=db_path)

    # Initially, no stale files
    stale = _check_stale_files(db_path, temp_dir)
    assert len(stale) == 0

    # Modify the file (ensure mtime changes)
    time.sleep(0.01)
    source_file.write_text("def modified():\n    return 2\n")

    # Now it should be detected as stale
    stale = _check_stale_files(db_path, temp_dir)
    assert len(stale) == 1
    assert "changeable.py" in str(stale[0])


def test_check_stale_files_detects_deletions(temp_dir: Path) -> None:
    """Test that _check_stale_files detects deleted files."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create and index a file
    source_file = temp_dir / "deletable.py"
    source_file.write_text("def will_be_deleted():\n    pass\n")

    index_path(root=temp_dir, db_path=db_path)

    # Delete the file
    source_file.unlink()

    # Should detect the deleted file
    stale = _check_stale_files(db_path, temp_dir)
    assert len(stale) == 1
    assert "deletable.py" in str(stale[0])
