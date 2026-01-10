"""
Reset command for ogrep.

Removes the index database, effectively clearing all indexed data
for the current scope.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ._common import resolve_db_path


def cmd_reset(args: argparse.Namespace) -> int:
    """
    Remove the index database for the current scope.

    Deletes the SQLite database file and cleans up empty parent
    directories. Requires confirmation unless --force is specified.

    Args:
        args: Parsed command-line arguments containing:
            - force: Skip confirmation prompt
            - db, profile, global_cache, repo_root: Scope options

    Returns:
        Exit code (0 for success, 1 if aborted).
    """
    repo_root = args.repo_root.resolve() if args.repo_root else Path.cwd()
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    if not db.exists():
        print(f"No database found at {db}")
        return 0

    if not args.force:
        confirm = input(f"Delete {db}? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Aborted.")
            return 1

    db.unlink()
    print(f"Removed {db}")

    # Clean up empty parent directories
    parent = db.parent
    try:
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass

    return 0
