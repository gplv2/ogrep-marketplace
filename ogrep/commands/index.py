"""
Index command for ogrep.

Indexes a directory by scanning files, chunking text, and storing
embeddings in a local SQLite database for semantic search.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..indexer import index_path
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
            - chunk_lines: Lines per chunk
            - overlap: Overlapping lines between chunks
            - max_bytes: Maximum file size to index

    Returns:
        Exit code (0 for success).
    """
    root = Path(args.path).resolve()
    repo_root = args.repo_root.resolve() if args.repo_root else root
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    index_path(
        root=root,
        db_path=db,
        model=args.model,
        dimensions=args.dimensions,
        chunk_lines=args.chunk_lines,
        overlap=args.overlap,
        max_bytes=args.max_bytes,
    )
    print(f"Indexed into {db}")
    return 0
