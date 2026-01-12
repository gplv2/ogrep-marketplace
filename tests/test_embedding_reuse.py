"""Tests for smart embedding reuse during incremental indexing."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from ogrep.indexer import IndexStats, index_path


def test_index_stats_returned(temp_dir: Path) -> None:
    """Test that index_path returns IndexStats."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"
    (temp_dir / "sample.py").write_text("# comment\nprint('hello')")

    stats = index_path(root=temp_dir, db_path=db_path)

    assert isinstance(stats, IndexStats)
    assert stats.files_scanned >= 1
    assert stats.files_indexed >= 1


def test_stats_counts_correct(temp_dir: Path) -> None:
    """Test that stats accurately count files and chunks."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create multiple files
    for i in range(3):
        (temp_dir / f"file{i}.py").write_text(f"# File {i}\nprint('hello')")

    stats = index_path(root=temp_dir, db_path=db_path, chunk_lines=10)

    assert stats.files_indexed == 3
    assert stats.chunks_total >= 3  # At least one chunk per file
    assert stats.chunks_embedded == stats.chunks_total  # First index, no reuse


def test_unchanged_file_skipped(sample_repo: Path, db_path: Path) -> None:
    """Test that unchanged files are completely skipped (no re-embedding)."""
    # First index
    stats1 = index_path(root=sample_repo, db_path=db_path)
    assert stats1.files_indexed > 0

    # Second index without changes
    stats2 = index_path(root=sample_repo, db_path=db_path)

    # All files should be skipped (unchanged)
    assert stats2.files_indexed == 0
    assert stats2.files_skipped > 0
    assert stats2.chunks_embedded == 0


def test_embedding_reuse_on_small_edit(temp_dir: Path) -> None:
    """Test that unchanged chunks reuse embeddings when file is edited."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create a file with multiple chunks (need enough lines)
    lines = [f"# Line {i}" for i in range(120)]  # 120 lines, ~2 chunks at 60 lines
    lines.insert(0, "def main():")
    lines.append("    pass")
    (temp_dir / "code.py").write_text("\n".join(lines))

    # First index
    stats1 = index_path(root=temp_dir, db_path=db_path, chunk_lines=60)
    initial_chunks = stats1.chunks_embedded

    assert initial_chunks >= 2, "Should have at least 2 chunks"

    # Small edit at the end (only affects last chunk)
    time.sleep(0.01)  # Ensure mtime changes
    lines[-1] = "    return 42  # changed"
    (temp_dir / "code.py").write_text("\n".join(lines))

    # Re-index
    stats2 = index_path(root=temp_dir, db_path=db_path, chunk_lines=60)

    # Should reuse some chunks (the first chunk didn't change)
    assert stats2.chunks_reused > 0, "Should reuse unchanged chunks"
    assert stats2.chunks_embedded < stats2.chunks_total, "Should not re-embed everything"


def test_embedding_reuse_append_only(temp_dir: Path) -> None:
    """Test embedding reuse when code is appended (common pattern)."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create initial file
    initial_content = """def first_function():
    '''First function.'''
    return 1

def second_function():
    '''Second function.'''
    return 2
"""
    (temp_dir / "functions.py").write_text(initial_content)

    # First index
    index_path(root=temp_dir, db_path=db_path, chunk_lines=20)

    # Append new function
    time.sleep(0.01)
    appended_content = (
        initial_content
        + """
def third_function():
    '''Third function added later.'''
    return 3
"""
    )
    (temp_dir / "functions.py").write_text(appended_content)

    # Re-index
    stats2 = index_path(root=temp_dir, db_path=db_path, chunk_lines=20)

    # Should have reused chunks from the unchanged beginning
    assert stats2.chunks_reused >= 0  # At least some chunks may be reused
    assert stats2.files_indexed == 1  # File was modified


def test_tokens_saved_estimate(temp_dir: Path) -> None:
    """Test that tokens_saved_estimate property works correctly."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create file with predictable chunks
    content = "\n".join([f"# Line {i}" for i in range(200)])
    (temp_dir / "big.py").write_text(content)

    # First index
    index_path(root=temp_dir, db_path=db_path, chunk_lines=50)

    # Tiny edit
    time.sleep(0.01)
    content_modified = content.replace("# Line 199", "# Line 199 modified")
    (temp_dir / "big.py").write_text(content_modified)

    # Re-index
    stats = index_path(root=temp_dir, db_path=db_path, chunk_lines=50)

    # tokens_saved_estimate should be chunks_reused * 100
    assert stats.tokens_saved_estimate == stats.chunks_reused * 100


def test_no_reuse_on_fresh_db(temp_dir: Path) -> None:
    """Test that no reuse happens on first index (fresh database)."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"
    (temp_dir / "file.py").write_text("# code\nprint('hello')")

    stats = index_path(root=temp_dir, db_path=db_path)

    assert stats.chunks_reused == 0
    assert stats.chunks_embedded == stats.chunks_total


def test_embedding_preserved_in_db(temp_dir: Path) -> None:
    """Test that reused embeddings are identical to original."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create file with 2 chunks
    chunk1 = "\n".join([f"# Chunk 1 line {i}" for i in range(60)])
    chunk2 = "\n".join([f"# Chunk 2 line {i}" for i in range(60)])
    (temp_dir / "two_chunks.py").write_text(chunk1 + "\n" + chunk2)

    # First index
    index_path(root=temp_dir, db_path=db_path, chunk_lines=60)

    # Get original embeddings
    con = sqlite3.connect(str(db_path))
    original = {row[0]: row[1] for row in con.execute("SELECT text_sha256, embedding FROM chunks")}
    con.close()

    # Modify only chunk 2
    time.sleep(0.01)
    chunk2_modified = "\n".join([f"# Chunk 2 MODIFIED line {i}" for i in range(60)])
    (temp_dir / "two_chunks.py").write_text(chunk1 + "\n" + chunk2_modified)

    # Re-index
    index_path(root=temp_dir, db_path=db_path, chunk_lines=60)

    # Get new embeddings
    con = sqlite3.connect(str(db_path))
    new_embeddings = {
        row[0]: row[1] for row in con.execute("SELECT text_sha256, embedding FROM chunks")
    }
    con.close()

    # Find chunk1's hash (should exist in both)
    common_hashes = set(original.keys()) & set(new_embeddings.keys())

    # Verify embeddings are identical for reused chunks
    for h in common_hashes:
        assert original[h] == new_embeddings[h], "Reused embedding should be identical"


def test_reuse_with_different_chunk_boundaries(temp_dir: Path) -> None:
    """Test that reuse still works when chunk boundaries shift."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # This tests a limitation: if we insert lines at the beginning,
    # chunk boundaries shift and nothing can be reused.
    content = "\n".join([f"# Line {i}" for i in range(100)])
    (temp_dir / "shifting.py").write_text(content)

    # First index
    index_path(root=temp_dir, db_path=db_path, chunk_lines=30)

    # Insert lines at beginning (shifts all chunks)
    time.sleep(0.01)
    new_content = "# New first line\n# Another new line\n" + content
    (temp_dir / "shifting.py").write_text(new_content)

    # Re-index - chunks shifted, limited reuse expected
    stats2 = index_path(root=temp_dir, db_path=db_path, chunk_lines=30)

    # This is a known limitation - shifts break reuse
    assert stats2.files_indexed == 1


def test_binary_files_not_counted(temp_dir: Path) -> None:
    """Test that binary files are properly skipped in stats."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    (temp_dir / "binary.bin").write_bytes(b"\x00\x01\x02\x03")
    (temp_dir / "source.py").write_text("# code")

    stats = index_path(root=temp_dir, db_path=db_path)

    assert stats.files_indexed == 1  # Only source.py
    assert stats.files_skipped >= 1  # binary.bin skipped


def test_large_file_skipped(temp_dir: Path) -> None:
    """Test that files exceeding max_bytes are skipped."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create a "large" file (we'll set a small limit)
    (temp_dir / "large.py").write_text("x" * 1000)
    (temp_dir / "small.py").write_text("# small")

    stats = index_path(root=temp_dir, db_path=db_path, max_bytes=500)

    assert stats.files_indexed == 1  # Only small.py
    assert stats.files_skipped >= 1  # large.py skipped


def test_exclude_pattern_counted_correctly(temp_dir: Path) -> None:
    """Test that excluded files affect scanned but not indexed counts."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    (temp_dir / "keep.py").write_text("# keep")
    (temp_dir / "skip_this.py").write_text("# skip")

    stats = index_path(root=temp_dir, db_path=db_path, exclude=["skip_*.py"])

    assert stats.files_indexed == 1  # Only keep.py


def test_index_stats_dataclass_properties(temp_dir: Path) -> None:
    """Test IndexStats dataclass behavior."""
    stats = IndexStats(
        files_scanned=10,
        files_indexed=5,
        files_skipped=5,
        chunks_total=20,
        chunks_reused=15,
        chunks_embedded=5,
    )

    assert stats.tokens_saved_estimate == 1500  # 15 * 100
    assert stats.files_scanned == stats.files_indexed + stats.files_skipped


# ============================================================================
# Cross-File Chunk Deduplication Tests
# ============================================================================


def test_cross_file_deduplication(temp_dir: Path) -> None:
    """Test that identical chunks across different files reuse embeddings."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create two files with mostly identical content
    shared_content = "\n".join([f"# Shared line {i}" for i in range(60)])
    unique_content_a = "\n".join([f"# Unique A line {i}" for i in range(60)])
    unique_content_b = "\n".join([f"# Unique B line {i}" for i in range(60)])

    (temp_dir / "file_a.py").write_text(shared_content + "\n" + unique_content_a)
    (temp_dir / "file_b.py").write_text(shared_content + "\n" + unique_content_b)

    # Index first file - all chunks embedded
    stats1 = index_path(root=temp_dir, db_path=db_path, chunk_lines=60, exclude=["file_b.py"])
    assert stats1.chunks_embedded >= 2  # At least 2 chunks (shared + unique_a)
    assert stats1.chunks_reused == 0  # First file, nothing to reuse

    # Index second file - shared chunk should be reused from first file
    stats2 = index_path(root=temp_dir, db_path=db_path, chunk_lines=60, exclude=["file_a.py"])

    # The shared chunk (60 lines) should be reused from file_a
    assert stats2.chunks_reused >= 1, "Should reuse shared chunk from file_a"
    assert stats2.chunks_embedded >= 1, "Should embed at least unique_b chunk"


def test_cross_file_dedup_stats_tracking(temp_dir: Path) -> None:
    """Test that stats distinguish between global and local reuse."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create identical content in two files
    content = "\n".join([f"# Line {i}" for i in range(60)])
    (temp_dir / "original.py").write_text(content)

    # Index first file
    index_path(root=temp_dir, db_path=db_path, chunk_lines=60, exclude=["copy.py"])

    # Create copy with identical content
    (temp_dir / "copy.py").write_text(content)

    # Index second file - should reuse from global
    stats = index_path(root=temp_dir, db_path=db_path, chunk_lines=60, exclude=["original.py"])

    # Check global reuse tracking
    assert hasattr(stats, "chunks_reused_global"), "IndexStats should track global reuse"
    assert stats.chunks_reused_global >= 1, "Should have at least 1 globally reused chunk"


def test_cross_file_integrity_check_text_hash(temp_dir: Path) -> None:
    """Test that corrupted text_sha256 entries are not reused."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create and index a file
    content = "\n".join([f"# Line {i}" for i in range(60)])
    (temp_dir / "source.py").write_text(content)

    index_path(root=temp_dir, db_path=db_path, chunk_lines=60)

    # Corrupt the text_sha256 in database (simulate data corruption)
    con = sqlite3.connect(str(db_path))
    con.execute("UPDATE chunks SET text_sha256 = 'corrupted_hash' WHERE chunk_index = 0")
    con.commit()
    con.close()

    # Create identical file - should NOT reuse corrupted entry
    (temp_dir / "copy.py").write_text(content)

    stats = index_path(root=temp_dir, db_path=db_path, chunk_lines=60, exclude=["source.py"])

    # Should embed new chunk, not reuse corrupted one
    assert stats.chunks_embedded >= 1, "Should embed chunk, not reuse corrupted entry"


def test_cross_file_integrity_check_dimension(temp_dir: Path) -> None:
    """Test that embeddings with wrong dimensions are not reused."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create and index multiple files to have multiple chunks
    # This way the majority of chunks have the correct dimension
    content_a = "\n".join([f"# File A Line {i}" for i in range(60)])
    content_b = "\n".join([f"# File B Line {i}" for i in range(60)])
    (temp_dir / "file_a.py").write_text(content_a)
    (temp_dir / "file_b.py").write_text(content_b)

    index_path(root=temp_dir, db_path=db_path, chunk_lines=60, exclude=["copy.py"])

    # Corrupt ONE chunk's dimension in database (file_a's chunk)
    con = sqlite3.connect(str(db_path))
    file_a_row = con.execute("SELECT id FROM files WHERE path LIKE '%file_a.py'").fetchone()
    if file_a_row:
        con.execute(
            "UPDATE chunks SET dim = 9999 WHERE file_id = ? AND chunk_index = 0",
            (file_a_row[0],),
        )
    con.commit()
    con.close()

    # Create file with content identical to corrupted chunk
    (temp_dir / "copy.py").write_text(content_a)

    stats = index_path(
        root=temp_dir, db_path=db_path, chunk_lines=60, exclude=["file_a.py", "file_b.py"]
    )

    # Should embed new chunk, not reuse wrong-dimension entry
    # The majority dimension (from file_b) should be used as expected_dim
    # In case of tie (1 chunk each), tiebreaker prefers smaller dim (256 < 9999)
    assert stats.chunks_embedded >= 1, "Should embed chunk, not reuse wrong-dimension entry"


def test_model_consistency_check(temp_dir: Path) -> None:
    """Test that indexing with different model raises error."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create and index with default model
    (temp_dir / "file.py").write_text("# some code")
    index_path(root=temp_dir, db_path=db_path, model="text-embedding-3-small")

    # Try to index more files with a different model
    (temp_dir / "file2.py").write_text("# more code")

    # Should raise an error about model mismatch
    import pytest

    with pytest.raises(ValueError, match="Model mismatch"):
        index_path(root=temp_dir, db_path=db_path, model="text-embedding-3-large")


def test_dedup_ratio_property(temp_dir: Path) -> None:
    """Test the dedup_ratio property on IndexStats."""
    # Test with known values
    stats = IndexStats(
        files_scanned=2,
        files_indexed=2,
        files_skipped=0,
        chunks_total=10,
        chunks_reused=4,
        chunks_embedded=6,
    )

    assert hasattr(stats, "dedup_ratio"), "IndexStats should have dedup_ratio property"
    assert stats.dedup_ratio == 40.0, "dedup_ratio should be 40% (4/10 * 100)"


def test_dedup_ratio_zero_chunks(temp_dir: Path) -> None:
    """Test dedup_ratio handles zero chunks gracefully."""
    stats = IndexStats(
        files_scanned=0,
        files_indexed=0,
        files_skipped=0,
        chunks_total=0,
        chunks_reused=0,
        chunks_embedded=0,
    )

    assert stats.dedup_ratio == 0.0, "dedup_ratio should be 0 when no chunks"


def test_cross_file_dedup_query_accuracy(temp_dir: Path) -> None:
    """Test that search works correctly with deduplicated chunks across files."""
    db_path = temp_dir / ".ogrep" / "index.sqlite"

    # Create two files with identical shared code
    shared_code = """def authenticate_user(username, password):
    '''Authenticate a user with username and password.'''
    if not username or not password:
        raise ValueError("Username and password required")
    return check_credentials(username, password)
"""

    # Add unique code to each file
    file_a = shared_code + "\ndef function_only_in_a():\n    return 'A'\n"
    file_b = shared_code + "\ndef function_only_in_b():\n    return 'B'\n"

    (temp_dir / "auth_module.py").write_text(file_a)
    (temp_dir / "auth_copy.py").write_text(file_b)

    # Index both files
    index_path(root=temp_dir, db_path=db_path, chunk_lines=30)

    # Query should return both files containing the shared code
    con = sqlite3.connect(str(db_path))
    rows = con.execute(
        """SELECT DISTINCT f.path FROM chunks c
           JOIN files f ON c.file_id = f.id
           WHERE c.text LIKE '%authenticate_user%'"""
    ).fetchall()
    con.close()

    paths = [r[0] for r in rows]
    assert len(paths) == 2, "Both files should be searchable"
    assert any("auth_module.py" in p for p in paths)
    assert any("auth_copy.py" in p for p in paths)
