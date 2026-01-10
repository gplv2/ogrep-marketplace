"""Chunking tests."""

from __future__ import annotations

from ogrep.chunking import Chunk, chunk_lines


def test_chunk_lines_basic() -> None:
    """Test basic chunking functionality."""
    text = "\n".join(f"Line {i}" for i in range(1, 11))
    chunks = chunk_lines(text, chunk_size=5, overlap=1)

    assert len(chunks) >= 2
    assert all(isinstance(c, Chunk) for c in chunks)


def test_chunk_lines_small_file() -> None:
    """Test chunking a file smaller than chunk size."""
    text = "Line 1\nLine 2\nLine 3"
    chunks = chunk_lines(text, chunk_size=10, overlap=2)

    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 3


def test_chunk_lines_empty() -> None:
    """Test chunking empty text."""
    chunks = chunk_lines("", chunk_size=10, overlap=2)
    assert len(chunks) == 0


def test_chunk_lines_whitespace_only() -> None:
    """Test chunking whitespace-only text."""
    chunks = chunk_lines("   \n\n   ", chunk_size=10, overlap=2)
    assert len(chunks) == 0


def test_chunk_overlap() -> None:
    """Test that chunks overlap correctly."""
    text = "\n".join(f"Line {i}" for i in range(1, 21))
    chunks = chunk_lines(text, chunk_size=10, overlap=3)

    # With overlap, later chunks should start before the previous chunk ends
    if len(chunks) >= 2:
        assert chunks[1].start_line < chunks[0].end_line + 1


def test_chunk_indices() -> None:
    """Test that chunk indices are sequential."""
    text = "\n".join(f"Line {i}" for i in range(1, 51))
    chunks = chunk_lines(text, chunk_size=10, overlap=2)

    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_chunk_line_numbers() -> None:
    """Test that line numbers are 1-indexed."""
    text = "First line\nSecond line\nThird line"
    chunks = chunk_lines(text, chunk_size=10, overlap=0)

    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 3
