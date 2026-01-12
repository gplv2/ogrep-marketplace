"""
Query command for ogrep.

Performs search against an indexed codebase, returning
the most relevant code chunks ranked by similarity score.

Supports three search modes:
- semantic: Embedding similarity only (original behavior)
- fulltext: SQLite FTS5 keyword matching only
- hybrid: Combined score (default) - best of both worlds

Supports --refresh flag to automatically reindex changed files before
querying, ensuring search results reflect the current codebase state.

Supports --json flag for structured output suitable for AI tools and
programmatic use, including full chunk text and metadata.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

from ..search import Hit
from ..search import query as query_db
from ._common import detect_language, require_embedding_config, resolve_db_path


def _get_index_info(db_path: Path) -> tuple[str, int] | None:
    """
    Get model and dimensions from the index.

    Args:
        db_path: Path to the SQLite database.

    Returns:
        Tuple of (model_name, dimensions) or None if index is empty.
    """
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute("SELECT model, dim FROM chunks LIMIT 1").fetchone()
        if row:
            return row[0], row[1]
        return None
    finally:
        con.close()


def _format_json_result(hit: Hit, repo_root: Path, rank: int) -> dict:
    """
    Format a single Hit for JSON output.

    Args:
        hit: The search result Hit object.
        repo_root: Repository root for relative path calculation.
        rank: The 1-indexed rank of this result.

    Returns:
        Dictionary with formatted result fields.
    """
    # Calculate relative path from repo root
    try:
        rel_path = str(Path(hit.path).relative_to(repo_root))
    except ValueError:
        rel_path = hit.path  # Fallback to absolute if not relative to root

    # Build chunk_ref: relative_path:chunk_index
    chunk_ref = f"{rel_path}:{hit.chunk_index}"

    return {
        "rank": rank,
        "chunk_ref": chunk_ref,
        "chunk_id": hit.chunk_id,
        "path": hit.path,
        "relative_path": rel_path,
        "start_line": hit.start_line,
        "end_line": hit.end_line,
        "score": round(hit.score, 4),
        "confidence": hit.confidence,
        "language": detect_language(hit.path),
        "text": hit.text,
    }


def _format_text_output(hits: list[Hit]) -> None:
    """
    Print hits in human-readable text format.

    Args:
        hits: List of Hit objects to format and print.
    """
    for h in hits:
        print(f"{h.path}:{h.start_line}-{h.end_line}  score={h.score:0.4f} ({h.confidence})")
        snippet = h.text.strip().replace("\n", "\\n")
        print(f"  {snippet[:240]}")


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
    Run a search query against the index.

    Supports three search modes:
    - semantic: Embedding similarity only (original behavior)
    - fulltext: SQLite FTS5 keyword matching only
    - hybrid: Combined score (default) - best of both worlds

    Args:
        args: Parsed command-line arguments containing:
            - query: Natural language search query
            - top: Number of results to return
            - mode: Search mode (semantic, fulltext, hybrid)
            - refresh: Whether to check for and reindex changed files
            - json: Whether to output results as JSON
            - db, profile, global_cache, repo_root: Scope options
            - model: OpenAI embedding model (must match indexed model)
            - dimensions: Embedding dimensions (must match indexed dimensions)

    Returns:
        Exit code (0 for success, 1 if database not found).

    Note:
        When --refresh is used, ogrep checks all indexed files for changes
        (mtime/size) and runs an incremental reindex before querying.
        This ensures search results reflect the current codebase state.

        When --json is used, output is structured JSON with full chunk text,
        language detection, and metadata. Recommended for AI tools.

        IMPORTANT: Without --refresh, queries may return stale results if
        files have been modified since the last index. AI tools and skills
        should always use --refresh to ensure accurate results.

        If FTS5 is unavailable and mode is hybrid/fulltext, falls back
        to semantic search with a warning.
    """
    if not require_embedding_config():
        return 1

    repo_root = args.repo_root.resolve() if args.repo_root else Path.cwd()
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)
    use_json = getattr(args, "json", False)

    if not db.exists():
        if use_json:
            print(json.dumps({"error": f"Database not found at {db}"}))
        else:
            print(f"Error: Database not found at {db}", file=sys.stderr)
            print("Run 'ogrep index .' first to create the index.", file=sys.stderr)
        return 1

    # Track refresh stats for JSON output
    refreshed_files = 0

    # Get index model/dimensions BEFORE any operations
    # This ensures --refresh uses the correct model, not CLI defaults
    index_info = _get_index_info(db)
    if index_info:
        index_model, index_dim = index_info
    else:
        # Empty index - use CLI args
        index_model, index_dim = args.model, args.dimensions

    # Handle --refresh: check for stale files and reindex if needed
    if getattr(args, "refresh", False):
        stale_files = _check_stale_files(db, repo_root)
        if stale_files:
            # Import here to avoid circular imports
            from ..indexer import index_path

            # Warn if user specified a different model than the index uses
            if args.model != index_model and index_info is not None:
                if not use_json:
                    print(
                        f"Note: Using index model ({index_model}), not -m {args.model}",
                        file=sys.stderr,
                    )

            if not use_json:
                print(f"Refreshing index ({len(stale_files)} changed files)...", file=sys.stderr)
            stats = index_path(
                root=repo_root,
                db_path=db,
                model=index_model,
                dimensions=index_dim,
            )
            refreshed_files = stats.files_indexed
            if not use_json and (stats.files_indexed > 0 or stats.chunks_reused > 0):
                print(
                    f"  Updated: {stats.files_indexed} files, "
                    f"{stats.chunks_embedded} new chunks "
                    f"({stats.chunks_reused} reused)",
                    file=sys.stderr,
                )

    # Get search mode
    search_mode = getattr(args, "mode", None)

    # Time the search
    start_time = time.perf_counter()

    hits, fts_available = query_db(
        db_path=db,
        q=args.query,
        top_k=args.top,
        model=index_model,
        dimensions=index_dim,
        mode=search_mode,
    )

    search_time_ms = int((time.perf_counter() - start_time) * 1000)

    # Warn if FTS5 was requested but not available
    if search_mode in ("hybrid", "fulltext") and not fts_available:
        if not use_json:
            print(
                "Warning: FTS5 index not available, using semantic search only.",
                file=sys.stderr,
            )
            print(
                "Run 'ogrep reindex .' to enable hybrid search.",
                file=sys.stderr,
            )

    # Get total chunk count for stats (model/dim already fetched above)
    con = sqlite3.connect(str(db))
    try:
        total_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    finally:
        con.close()

    if use_json:
        # Build JSON output using helper
        results = [
            _format_json_result(h, repo_root, rank)
            for rank, h in enumerate(hits, 1)
        ]

        # Calculate confidence distribution
        confidence_summary = {"high": 0, "medium": 0, "low": 0, "very_low": 0}
        for h in hits:
            confidence_summary[h.confidence] += 1

        output = {
            "query": args.query,
            "results": results,
            "stats": {
                "total_results": len(hits),
                "total_chunks": total_chunks,
                "search_time_ms": search_time_ms,
                "search_mode": search_mode or "hybrid",
                "fts_available": fts_available,
                "index_model": index_model,
                "index_dimensions": index_dim,
                "refreshed_files": refreshed_files,
                "confidence_summary": confidence_summary,
            },
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output using helper
        _format_text_output(hits)

    return 0
