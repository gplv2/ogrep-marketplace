"""
Reset command for ogrep.

Removes the index database, effectively clearing all indexed data
for the current scope.
"""

from __future__ import annotations

import argparse
import json
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
            - json: Whether to output as JSON
            - db, profile, global_cache, repo_root: Scope options

    Returns:
        Exit code (0 for success, 1 if aborted).
    """
    repo_root = args.repo_root.resolve() if args.repo_root else Path.cwd()
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)
    use_json = getattr(args, "json", False)

    if not db.exists():
        if use_json:
            print(json.dumps({"database": str(db), "existed": False, "removed": False}))
        else:
            print(f"No database found at {db}")
        return 0

    if not args.force:
        import sys

        if not sys.stdin.isatty():
            if use_json:
                print(json.dumps({
                    "error": "Non-interactive mode requires --force (-f) flag",
                    "database": str(db),
                }))
            else:
                print("Non-interactive mode requires --force (-f) flag.")
            return 1
        confirm = input(f"Delete {db}? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            if use_json:
                print(json.dumps({
                    "database": str(db),
                    "existed": True,
                    "removed": False,
                    "aborted": True,
                }))
            else:
                print("Aborted.")
            return 1

    db.unlink()

    # Clean up empty parent directories
    parent = db.parent
    parent_removed = False
    try:
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent_removed = True
    except OSError:
        pass

    if use_json:
        print(json.dumps({
            "database": str(db),
            "existed": True,
            "removed": True,
            "parent_removed": parent_removed,
        }))
    else:
        print(f"Removed {db}")

    return 0
