"""
Reindex command for ogrep.

Force rebuilds the index from scratch by removing the existing
database and re-indexing the entire directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..indexer import index_path
from ._common import resolve_db_path


def cmd_reindex(args: argparse.Namespace) -> int:
    """
    Force rebuild the index from scratch.

    Removes any existing index database and performs a fresh index
    of the target directory. Useful when changing embedding models
    or chunk sizes, or when the index becomes corrupted.

    Args:
        args: Parsed command-line arguments containing:
            - path: Directory to index (default: current directory)
            - db, profile, global_cache, repo_root: Scope options
            - model: OpenAI embedding model name
            - dimensions: Embedding dimensions
            - chunk_lines: Lines per chunk
            - overlap: Overlapping lines between chunks
            - max_bytes: Maximum file size to index
            - exclude: List of glob patterns to exclude

    Returns:
        Exit code (0 for success).
    """
    root = Path(args.path).resolve()
    repo_root = args.repo_root.resolve() if args.repo_root else root
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    # Remove existing database
    if db.exists():
        db.unlink()
        print(f"Removed existing index at {db}")

    # Reindex
    index_path(
        root=root,
        db_path=db,
        model=args.model,
        dimensions=args.dimensions,
        chunk_lines=args.chunk_lines,
        overlap=args.overlap,
        max_bytes=args.max_bytes,
        exclude=args.exclude,
    )
    print(f"Reindexed into {db}")
    return 0
