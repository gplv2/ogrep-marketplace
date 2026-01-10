"""
Shared utilities for ogrep CLI commands.

This module provides common functionality used across multiple commands,
including database path resolution and argument parsing helpers.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def _repo_hash(root: Path) -> str:
    """
    Generate a short hash from repository path for global cache keying.

    Args:
        root: The repository root path.

    Returns:
        A 12-character hex string derived from the absolute path.
    """
    return hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12]


def resolve_db_path(
    db_arg: str | None,
    profile: str | None,
    global_cache: bool,
    repo_root: Path | None = None,
) -> Path:
    """
    Resolve the database path based on scope flags.

    Determines the appropriate SQLite database location based on the
    provided scope options. This enables multi-repo setups without
    index pollution between projects.

    Priority (highest to lowest):
        1. Explicit --db path
        2. --global-cache: ~/.cache/ogrep/<repo_hash>/index.sqlite
        3. --profile: .ogrep/<profile>/index.sqlite
        4. Default: .ogrep/index.sqlite

    Args:
        db_arg: Explicit database path from --db flag.
        profile: Profile name from --profile flag.
        global_cache: Whether to use global cache from --global-cache flag.
        repo_root: Repository root path (defaults to current directory).

    Returns:
        Resolved Path to the SQLite database file.

    Examples:
        >>> resolve_db_path(None, None, False)
        PosixPath('.ogrep/index.sqlite')

        >>> resolve_db_path(None, "dev", False)
        PosixPath('.ogrep/dev/index.sqlite')

        >>> resolve_db_path("/custom/path.db", None, False)
        PosixPath('/custom/path.db')
    """
    if db_arg:
        return Path(db_arg)

    root = repo_root or Path.cwd()

    if global_cache:
        cache_dir = Path.home() / ".cache" / "ogrep" / _repo_hash(root)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "index.sqlite"

    if profile:
        return root / ".ogrep" / profile / "index.sqlite"

    return root / ".ogrep" / "index.sqlite"


def add_scope_args(parser: argparse.ArgumentParser) -> None:
    """
    Add common scope/fencing arguments to an argument parser.

    Adds the standard set of arguments for controlling index scope:
        --db, --profile, --global-cache, --repo-root

    These arguments allow users to manage multiple indexes and prevent
    cross-repository pollution in monorepo or multi-project setups.

    Args:
        parser: The argparse parser or subparser to add arguments to.
    """
    parser.add_argument(
        "--db",
        default=None,
        help="Explicit SQLite DB path (overrides all other scope options)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Profile name for multiple indexes per repo (.ogrep/<profile>/index.sqlite)",
    )
    parser.add_argument(
        "--global-cache",
        action="store_true",
        help="Use global cache at ~/.cache/ogrep/<repo_hash>/index.sqlite",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Explicit repository root (default: current directory)",
    )
