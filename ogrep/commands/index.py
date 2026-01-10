"""
Index command for ogrep.

Indexes a directory by scanning files, chunking text, and storing
embeddings in a local SQLite database for semantic search.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..indexer import index_path
from ..models import get_optimal_chunk_lines
from ._common import resolve_db_path


def cmd_index(args: argparse.Namespace) -> int:
    """
    Index a directory for semantic search.

    Scans the target directory for text files, splits them into chunks,
    generates embeddings via OpenAI API, and stores everything in a
    local SQLite database.

    Args:
        args: Parsed command-line arguments containing:
            - path: Directory to index (default: current directory)
            - db, profile, global_cache, repo_root: Scope options
            - model: OpenAI embedding model name
            - dimensions: Embedding dimensions (model-specific)
            - chunk_lines: Lines per chunk (None = model-specific default)
            - overlap: Overlapping lines between chunks
            - max_bytes: Maximum file size to index
            - exclude: Additional glob patterns to exclude
            - include: Glob patterns to include (override excludes)

    Returns:
        Exit code (0 for success).
    """
    root = Path(args.path).resolve()
    repo_root = args.repo_root.resolve() if args.repo_root else root
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    # Use model-specific optimal chunk size if not explicitly specified
    chunk_lines = args.chunk_lines
    if chunk_lines is None:
        chunk_lines = get_optimal_chunk_lines(args.model)

    stats = index_path(
        root=root,
        db_path=db,
        model=args.model,
        dimensions=args.dimensions,
        chunk_lines=chunk_lines,
        overlap=args.overlap,
        max_bytes=args.max_bytes,
        exclude=args.exclude,
        include=args.include,
    )

    # Display indexing statistics
    print(f"Indexed into {db}")
    print(f"  Files: {stats.files_indexed} indexed, {stats.files_skipped} skipped")
    if stats.chunks_total > 0:
        print(f"  Chunks: {stats.chunks_total} total", end="")
        if stats.chunks_reused > 0:
            print(f" ({stats.chunks_reused} reused, ~{stats.tokens_saved_estimate} tokens saved)")
        else:
            print(f" ({stats.chunks_embedded} embedded)")
    return 0
