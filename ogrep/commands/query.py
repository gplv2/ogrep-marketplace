"""
Query command for ogrep.

Performs semantic search against an indexed codebase, returning
the most relevant code chunks ranked by cosine similarity.

Supports --refresh flag to automatically reindex changed files before
querying, ensuring search results reflect the current codebase state.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from ..search import query as query_db
from ._common import resolve_db_path


def _check_stale_files(db_path: Path, repo_root: Path) -> list[Path]:
    """
    Check for files that have changed since last indexing.

    Compares current file mtime/size against stored values to detect
    files that need reindexing.

    Args:
        db_path: Path to the SQLite database.
        repo_root: Repository root to resolve relative paths.

    Returns:
        List of file paths that have changed or been deleted.
    """
    stale: list[Path] = []
    con = sqlite3.connect(str(db_path))

    try:
        rows = con.execute("SELECT path, mtime_ns, size FROM files").fetchall()
        for path_str, mtime_ns, size in rows:
            file_path = Path(path_str)
            if not file_path.exists():
                # File was deleted
                stale.append(file_path)
            else:
                # Check if file was modified
                stat = file_path.stat()
                if stat.st_mtime_ns != mtime_ns or stat.st_size != size:
                    stale.append(file_path)
    finally:
        con.close()

    return stale


def cmd_query(args: argparse.Namespace) -> int:
    """
    Run a semantic query against the index.

    Embeds the query text and searches for similar code chunks
    in the database using cosine similarity scoring.

    Args:
        args: Parsed command-line arguments containing:
            - query: Natural language search query
            - top: Number of results to return
            - refresh: Whether to check for and reindex changed files
            - db, profile, global_cache, repo_root: Scope options
            - model: OpenAI embedding model (must match indexed model)
            - dimensions: Embedding dimensions (must match indexed dimensions)

    Returns:
        Exit code (0 for success, 1 if database not found).

    Note:
        When --refresh is used, ogrep checks all indexed files for changes
        (mtime/size) and runs an incremental reindex before querying.
        This ensures search results reflect the current codebase state.

        IMPORTANT: Without --refresh, queries may return stale results if
        files have been modified since the last index. AI tools and skills
        should always use --refresh to ensure accurate results.
    """
    repo_root = args.repo_root.resolve() if args.repo_root else Path.cwd()
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    if not db.exists():
        print(f"Error: Database not found at {db}", file=sys.stderr)
        print("Run 'ogrep index .' first to create the index.", file=sys.stderr)
        return 1

    # Handle --refresh: check for stale files and reindex if needed
    if getattr(args, "refresh", False):
        stale_files = _check_stale_files(db, repo_root)
        if stale_files:
            # Import here to avoid circular imports
            from ..indexer import index_path

            print(f"Refreshing index ({len(stale_files)} changed files)...", file=sys.stderr)
            stats = index_path(
                root=repo_root,
                db_path=db,
                model=args.model,
                dimensions=args.dimensions,
            )
            if stats.files_indexed > 0 or stats.chunks_reused > 0:
                print(
                    f"  Updated: {stats.files_indexed} files, "
                    f"{stats.chunks_embedded} new chunks "
                    f"({stats.chunks_reused} reused)",
                    file=sys.stderr,
                )

    hits = query_db(
        db_path=db,
        q=args.query,
        top_k=args.top,
        model=args.model,
        dimensions=args.dimensions,
    )

    for h in hits:
        print(f"{h.path}:{h.start_line}-{h.end_line}  score={h.score:0.4f}")
        snippet = h.text.strip().replace("\n", "\\n")
        print(f"  {snippet[:240]}")

    return 0
