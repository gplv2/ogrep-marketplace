"""
Status command for ogrep.

Displays index statistics including file count, chunk count,
embedding model info, and database size.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from ._common import resolve_db_path


def _format_size(size_bytes: int) -> str:
    """
    Format byte size into human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted string (e.g., "1.5 MB", "256 KB", "512 bytes").
    """
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} bytes"


def cmd_status(args: argparse.Namespace) -> int:
    """
    Show index status and statistics.

    Displays information about the current index including:
        - Database location
        - Number of indexed files
        - Number of chunks
        - Embedding model and dimensions
        - Database file size

    Args:
        args: Parsed command-line arguments containing:
            - db, profile, global_cache, repo_root: Scope options
            - json: Whether to output as JSON

    Returns:
        Exit code (0 for success).
    """
    repo_root = args.repo_root.resolve() if args.repo_root else Path.cwd()
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)
    use_json = getattr(args, "json", False)

    if not db.exists():
        if use_json:
            print(json.dumps({
                "database": str(db),
                "status": "not_indexed",
                "indexed": False,
            }))
        else:
            print(f"Database: {db}")
            print("Status: Not indexed")
        return 0

    con = sqlite3.connect(str(db))
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM files")
    file_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM chunks")
    chunk_count = cur.fetchone()[0]

    cur.execute("SELECT model, dim FROM chunks LIMIT 1")
    row = cur.fetchone()
    model = row[0] if row else None
    dim = row[1] if row else None

    # Check for AST mode metadata
    ast_mode = None
    try:
        cur.execute("SELECT value FROM index_metadata WHERE key = 'ast_mode'")
        ast_row = cur.fetchone()
        if ast_row:
            ast_mode = ast_row[0] == "true"
    except sqlite3.OperationalError:
        # index_metadata table doesn't exist (older index)
        pass

    size_bytes = db.stat().st_size
    size_str = _format_size(size_bytes)

    con.close()

    if use_json:
        result = {
            "database": str(db),
            "status": "indexed",
            "indexed": True,
            "files": file_count,
            "chunks": chunk_count,
            "model": model,
            "dimensions": dim,
            "size_bytes": size_bytes,
            "size_human": size_str,
        }
        if ast_mode is not None:
            result["ast_mode"] = ast_mode
        print(json.dumps(result))
    else:
        print(f"Database: {db}")
        print("Status: Indexed")
        print(f"Files: {file_count}")
        print(f"Chunks: {chunk_count}")
        print(f"Model: {model}")
        print(f"Dimensions: {dim}")
        if ast_mode is not None:
            print(f"AST Mode: {'enabled' if ast_mode else 'disabled'}")
        print(f"Size: {size_str}")

    return 0
