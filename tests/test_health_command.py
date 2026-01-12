"""Tests for the ogrep health command."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pytest

from ogrep.commands.health import cmd_health
from ogrep.db import connect


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary database with test data."""
    db_path = tmp_path / ".ogrep" / "index.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = connect(db_path)

    # Insert test file
    con.execute(
        "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
        ("test.py", 123456789, 100, "abc123"),
    )
    file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Insert test chunks
    for i in range(3):
        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                file_id,
                i,
                i * 10,
                (i + 1) * 10,
                f"chunk {i} text",
                f"sha_{i}",
                b"\x00" * 1536 * 4,
                1536,
                "test-model",
            ),
        )

    con.commit()
    con.close()

    return db_path


def test_health_no_database(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test health command when database doesn't exist."""
    args = argparse.Namespace(
        db=tmp_path / "nonexistent.sqlite",
        profile=None,
        global_cache=False,
        repo_root=tmp_path,
        vacuum=False,
        rebuild_fts=False,
        reindex=False,
        integrity=False,
        full=False,
    )

    result = cmd_health(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Not indexed" in captured.out


def test_health_basic(temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test basic health output."""
    args = argparse.Namespace(
        db=temp_db,
        profile=None,
        global_cache=False,
        repo_root=temp_db.parent.parent,
        vacuum=False,
        rebuild_fts=False,
        reindex=False,
        integrity=False,
        full=False,
    )

    result = cmd_health(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Tables" in captured.out
    assert "chunks" in captured.out
    assert "files" in captured.out
    assert "Indexes" in captured.out
    assert "SQLite Info" in captured.out
    assert "Quick Check" in captured.out
    assert "OK" in captured.out
    assert "Healthy" in captured.out


def test_health_vacuum(temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test vacuum flag."""
    args = argparse.Namespace(
        db=temp_db,
        profile=None,
        global_cache=False,
        repo_root=temp_db.parent.parent,
        vacuum=True,
        rebuild_fts=False,
        reindex=False,
        integrity=False,
        full=False,
    )

    result = cmd_health(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Vacuum" in captured.out
    assert "Before:" in captured.out
    assert "After:" in captured.out


def test_health_rebuild_fts(temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test rebuild-fts flag."""
    args = argparse.Namespace(
        db=temp_db,
        profile=None,
        global_cache=False,
        repo_root=temp_db.parent.parent,
        vacuum=False,
        rebuild_fts=True,
        reindex=False,
        integrity=False,
        full=False,
    )

    result = cmd_health(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Rebuild FTS5" in captured.out
    assert "Indexed 3 chunks" in captured.out

    # Verify FTS5 was actually rebuilt
    con = sqlite3.connect(str(temp_db))
    count = con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    con.close()
    assert count == 3


def test_health_integrity(temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test integrity flag."""
    args = argparse.Namespace(
        db=temp_db,
        profile=None,
        global_cache=False,
        repo_root=temp_db.parent.parent,
        vacuum=False,
        rebuild_fts=False,
        reindex=False,
        integrity=True,
        full=False,
    )

    result = cmd_health(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Full Integrity Check" in captured.out
    assert "OK" in captured.out


def test_health_full(temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test full flag runs vacuum, rebuild-fts, and integrity."""
    args = argparse.Namespace(
        db=temp_db,
        profile=None,
        global_cache=False,
        repo_root=temp_db.parent.parent,
        vacuum=False,
        rebuild_fts=False,
        reindex=False,
        integrity=False,
        full=True,
    )

    result = cmd_health(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Vacuum" in captured.out
    assert "Rebuild FTS5" in captured.out
    assert "Full Integrity Check" in captured.out


def test_health_shows_fts5_stats_after_rebuild(
    temp_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that FTS5 stats show after rebuild."""
    # First rebuild FTS5
    args = argparse.Namespace(
        db=temp_db,
        profile=None,
        global_cache=False,
        repo_root=temp_db.parent.parent,
        vacuum=False,
        rebuild_fts=True,
        reindex=False,
        integrity=False,
        full=False,
    )
    cmd_health(args)

    # Now run health again to see FTS5 stats
    args.rebuild_fts = False
    result = cmd_health(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "FTS5 Stats" in captured.out
    assert "Rows indexed: 3" in captured.out


@pytest.fixture
def temp_db_with_dedup(tmp_path: Path) -> Path:
    """Create a temporary database with duplicate chunks (same text_sha256)."""
    db_path = tmp_path / ".ogrep" / "index.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = connect(db_path)

    # Insert test files
    for i in range(3):
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            (f"file{i}.py", 123456789, 100, f"file_sha_{i}"),
        )
    file_ids = [row[0] for row in con.execute("SELECT id FROM files").fetchall()]

    # Insert chunks with some duplicates:
    # - file1 and file2 share "common_sha" (2 chunks with same hash)
    # - file3 has unique chunks
    # Total: 5 chunks, 4 unique hashes, 1 duplicate
    chunks_data = [
        (file_ids[0], 0, 0, 10, "common code block", "common_sha"),
        (file_ids[0], 1, 10, 20, "file1 unique", "unique_sha_1"),
        (file_ids[1], 0, 0, 10, "common code block", "common_sha"),  # Duplicate!
        (file_ids[1], 1, 10, 20, "file2 unique", "unique_sha_2"),
        (file_ids[2], 0, 0, 10, "file3 unique", "unique_sha_3"),
    ]

    for file_id, chunk_idx, start, end, text, sha in chunks_data:
        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, chunk_idx, start, end, text, sha, b"\x00" * 1536 * 4, 1536, "test-model"),
        )

    con.commit()
    con.close()

    return db_path


def test_health_shows_dedup_stats(
    temp_db_with_dedup: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that health command shows deduplication statistics."""
    args = argparse.Namespace(
        db=temp_db_with_dedup,
        profile=None,
        global_cache=False,
        repo_root=temp_db_with_dedup.parent.parent,
        vacuum=False,
        rebuild_fts=False,
        reindex=False,
        integrity=False,
        full=False,
    )

    result = cmd_health(args)

    assert result == 0
    captured = capsys.readouterr()

    # Should show Dedup Stats section
    assert "Dedup Stats" in captured.out
    # Should show total chunks: 5
    assert "5" in captured.out
    # Should show unique hashes: 4
    assert "4" in captured.out
    # Should show 1 duplicated (embedding saved)
    assert "1" in captured.out or "20%" in captured.out


def test_health_dedup_no_duplicates(temp_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test dedup stats when there are no duplicates."""
    args = argparse.Namespace(
        db=temp_db,
        profile=None,
        global_cache=False,
        repo_root=temp_db.parent.parent,
        vacuum=False,
        rebuild_fts=False,
        reindex=False,
        integrity=False,
        full=False,
    )

    result = cmd_health(args)

    assert result == 0
    captured = capsys.readouterr()

    # Should show Dedup Stats section
    assert "Dedup Stats" in captured.out
    # With no duplicates, should show 0% or "none"
    assert "0%" in captured.out or "No duplicates" in captured.out
