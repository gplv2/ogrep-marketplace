"""
Clean command for ogrep.

Removes stale entries from the index where the source files
no longer exist on disk, and optionally compacts the database.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from ._common import resolve_db_path


def cmd_clean(args: argparse.Namespace) -> int:
    """
    Remove stale entries and optionally vacuum the database.

    Scans the index for files that no longer exist on disk and
    removes their entries. This keeps the index lean and prevents
    stale results from appearing in searches.

    Args:
        args: Parsed command-line arguments containing:
            - vacuum: Whether to compact the database after cleaning
            - db, profile, global_cache, repo_root: Scope options

    Returns:
        Exit code (0 for success).
    """
    repo_root = args.repo_root.resolve() if args.repo_root else Path.cwd()
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    if not db.exists():
        print(f"No database found at {db}")
        return 0

    con = sqlite3.connect(str(db))
    cur = con.cursor()

    try:
        # Find files that no longer exist
        cur.execute("SELECT id, path FROM files")
        rows = cur.fetchall()

        removed = 0
        for file_id, path in rows:
            if not Path(path).exists():
                cur.execute("DELETE FROM files WHERE id = ?", (file_id,))
                removed += 1

        con.commit()
        print(f"Removed {removed} stale file entries")

        if args.vacuum:
            print("Running VACUUM...")
            con.execute("VACUUM")
            print("Database compacted")

    except KeyboardInterrupt:
        con.close()
        print("\n\nInterrupted by user (Ctrl-C).")
        print("Clean cancelled. Partial changes may have been saved.")
        return 130  # Standard SIGINT exit code (128 + 2)

    con.close()
    return 0
