"""
Reindex command for ogrep.

Force rebuilds the index from scratch by removing the existing
database and re-indexing the entire directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import sqlite3

from ..db import log_history
from ..indexer import index_path
from ..models import get_optimal_chunk_lines, get_optimal_overlap
from ._common import require_embedding_config, resolve_db_path


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
            - chunk_lines: Lines per chunk (None = model-specific default)
            - overlap: Overlapping lines between chunks (None = model-specific default)
            - max_bytes: Maximum file size to index
            - exclude: Additional glob patterns to exclude
            - include: Glob patterns to include (override excludes)
            - json: Whether to output as JSON

    Returns:
        Exit code (0 for success, 1 for configuration error).
    """
    use_json = getattr(args, "json", False)

    if not require_embedding_config():
        if use_json:
            print(json.dumps({"error": "Missing OPENAI_API_KEY environment variable"}))
        return 1

    root = Path(args.path).resolve()
    # If root is a file, use its parent directory for repo_root
    if args.repo_root:
        repo_root = args.repo_root.resolve()
    elif root.is_file():
        repo_root = root.parent
    else:
        repo_root = root
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    # Use model-specific optimal settings if not explicitly specified
    chunk_lines = args.chunk_lines
    if chunk_lines is None:
        chunk_lines = get_optimal_chunk_lines(args.model)

    overlap = args.overlap
    if overlap is None:
        overlap = get_optimal_overlap(args.model)

    # Remove existing database
    removed_existing = False
    if db.exists():
        db.unlink()
        removed_existing = True
        if not use_json:
            print(f"Removed existing index at {db}")

    # Reindex
    try:
        stats = index_path(
            root=root,
            db_path=db,
            model=args.model,
            dimensions=args.dimensions,
            chunk_lines=chunk_lines,
            overlap=overlap,
            max_bytes=args.max_bytes,
            exclude=args.exclude,
            include=args.include,
            ast=getattr(args, "ast", False),
        )
    except KeyboardInterrupt:
        if use_json:
            print(json.dumps({"error": "Interrupted by user (Ctrl-C)"}))
        else:
            print("\n\nInterrupted by user (Ctrl-C).")
            print("Partial progress may have been saved to the index.")
            print("Run 'ogrep reindex .' again to rebuild from scratch.")
        return 130  # Standard SIGINT exit code (128 + 2)

    # Log reindex action to history (overrides the "index" entry from index_path)
    # We update the most recent entry to be "reindex" for clarity
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "UPDATE index_history SET action = 'reindex' WHERE id = (SELECT MAX(id) FROM index_history)"
        )
        con.commit()
    except sqlite3.OperationalError:
        pass  # History table might not exist in older databases
    finally:
        con.close()

    if use_json:
        print(json.dumps({
            "database": str(db),
            "removed_existing": removed_existing,
            "files_indexed": stats.files_indexed,
            "files_skipped": stats.files_skipped,
            "files_scanned": stats.files_scanned,
            "chunks_total": stats.chunks_total,
            "chunks_embedded": stats.chunks_embedded,
            "chunks_reused": stats.chunks_reused,
            "tokens_saved_estimate": stats.tokens_saved_estimate,
        }))
    else:
        print(f"Reindexed into {db}")
        print(f"  Files: {stats.files_indexed} indexed, {stats.files_skipped} skipped")
        if stats.chunks_total > 0:
            print(f"  Chunks: {stats.chunks_total} ({stats.chunks_embedded} embedded)")

    return 0
