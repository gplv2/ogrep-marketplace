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

from ..search import query as query_db
from ._common import detect_language, require_embedding_config, resolve_db_path


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

    # Handle --refresh: check for stale files and reindex if needed
    if getattr(args, "refresh", False):
        stale_files = _check_stale_files(db, repo_root)
        if stale_files:
            # Import here to avoid circular imports
            from ..indexer import index_path

            if not use_json:
                print(f"Refreshing index ({len(stale_files)} changed files)...", file=sys.stderr)
            stats = index_path(
                root=repo_root,
                db_path=db,
                model=args.model,
                dimensions=args.dimensions,
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
        model=args.model,
        dimensions=args.dimensions,
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

    # Get index metadata for stats
    con = sqlite3.connect(str(db))
    try:
        index_info = con.execute("SELECT model, dim FROM chunks LIMIT 1").fetchone()
        total_chunks = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    finally:
        con.close()

    index_model = index_info[0] if index_info else None
    index_dim = index_info[1] if index_info else None

    if use_json:
        # Build JSON output
        results = []
        for rank, h in enumerate(hits, 1):
            # Calculate relative path from repo root
            try:
                rel_path = str(Path(h.path).relative_to(repo_root))
            except ValueError:
                rel_path = h.path  # Fallback to absolute if not relative to root

            # Build chunk_ref: relative_path:chunk_index (human-readable reference)
            chunk_ref = f"{rel_path}:{h.chunk_index}"

            results.append({
                "rank": rank,
                "chunk_ref": chunk_ref,
                "chunk_id": h.chunk_id,
                "path": h.path,
                "relative_path": rel_path,
                "start_line": h.start_line,
                "end_line": h.end_line,
                "score": round(h.score, 4),
                "confidence": h.confidence,
                "language": detect_language(h.path),
                "text": h.text,
            })

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
        # Human-readable output (truncated snippets)
        for h in hits:
            print(f"{h.path}:{h.start_line}-{h.end_line}  score={h.score:0.4f} ({h.confidence})")
            snippet = h.text.strip().replace("\n", "\\n")
            print(f"  {snippet[:240]}")

    return 0
