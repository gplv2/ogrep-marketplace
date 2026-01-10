"""
Command-line interface for ogrep.

This module provides the main entry point and argument parsing for the
ogrep semantic search tool. Individual command implementations are
located in the `ogrep.commands` subpackage.

Usage:
    ogrep index .              # Index current directory
    ogrep query "search text"  # Semantic search
    ogrep status               # Show index statistics
    ogrep reset --force        # Delete index
    ogrep reindex .            # Rebuild from scratch
    ogrep clean --vacuum       # Remove stale entries
"""

from __future__ import annotations

import argparse
import sys

from .commands import (
    cmd_clean,
    cmd_index,
    cmd_query,
    cmd_reindex,
    cmd_reset,
    cmd_status,
)
from .commands._common import add_scope_args

__version__ = "0.1.0"


def _build_parser() -> argparse.ArgumentParser:
    """
    Build and return the argument parser with all subcommands.

    Returns:
        Configured ArgumentParser with all ogrep subcommands.
    """
    p = argparse.ArgumentParser(
        prog="ogrep",
        description="Local semantic grep powered by SQLite and OpenAI embeddings",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")

    # index command
    p_index = sub.add_parser("index", help="Index a directory for semantic search")
    p_index.add_argument("path", nargs="?", default=".", help="Root path (default: .)")
    add_scope_args(p_index)
    p_index.add_argument(
        "--model",
        default="text-embedding-3-small",
        help="OpenAI embedding model (default: text-embedding-3-small)",
    )
    p_index.add_argument(
        "--dimensions",
        type=int,
        default=None,
        help="Embedding dimensions (default: model default)",
    )
    p_index.add_argument(
        "--chunk-lines",
        type=int,
        default=120,
        help="Lines per chunk (default: 120)",
    )
    p_index.add_argument(
        "--overlap",
        type=int,
        default=20,
        help="Overlapping lines between chunks (default: 20)",
    )
    p_index.add_argument(
        "--max-bytes",
        type=int,
        default=2_000_000,
        help="Max file size in bytes (default: 2MB)",
    )
    p_index.set_defaults(func=cmd_index)

    # query command
    p_query = sub.add_parser("query", help="Semantic search against the index")
    p_query.add_argument("query", help="Natural language search query")
    add_scope_args(p_query)
    p_query.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of results (default: 10)",
    )
    p_query.add_argument(
        "--model",
        default="text-embedding-3-small",
        help="OpenAI embedding model (must match indexed model)",
    )
    p_query.add_argument(
        "--dimensions",
        type=int,
        default=None,
        help="Embedding dimensions (must match indexed dimensions)",
    )
    p_query.set_defaults(func=cmd_query)

    # reset command
    p_reset = sub.add_parser("reset", help="Remove the index database")
    add_scope_args(p_reset)
    p_reset.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation prompt",
    )
    p_reset.set_defaults(func=cmd_reset)

    # reindex command
    p_reindex = sub.add_parser("reindex", help="Force rebuild index from scratch")
    p_reindex.add_argument("path", nargs="?", default=".", help="Root path (default: .)")
    add_scope_args(p_reindex)
    p_reindex.add_argument(
        "--model",
        default="text-embedding-3-small",
        help="OpenAI embedding model",
    )
    p_reindex.add_argument(
        "--dimensions",
        type=int,
        default=None,
        help="Embedding dimensions",
    )
    p_reindex.add_argument(
        "--chunk-lines",
        type=int,
        default=120,
        help="Lines per chunk",
    )
    p_reindex.add_argument(
        "--overlap",
        type=int,
        default=20,
        help="Overlapping lines between chunks",
    )
    p_reindex.add_argument(
        "--max-bytes",
        type=int,
        default=2_000_000,
        help="Max file size in bytes",
    )
    p_reindex.set_defaults(func=cmd_reindex)

    # clean command
    p_clean = sub.add_parser("clean", help="Remove stale entries from index")
    add_scope_args(p_clean)
    p_clean.add_argument(
        "--vacuum",
        action="store_true",
        help="Compact database after cleaning",
    )
    p_clean.set_defaults(func=cmd_clean)

    # status command
    p_status = sub.add_parser("status", help="Show index status and statistics")
    add_scope_args(p_status)
    p_status.set_defaults(func=cmd_status)

    return p


def main() -> None:
    """
    Main entry point for the ogrep CLI.

    Parses command-line arguments and dispatches to the appropriate
    command handler. Exit code is determined by the command's return value.
    """
    parser = _build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
