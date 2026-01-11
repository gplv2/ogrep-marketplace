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
    ogrep models               # List available models

Environment Variables:
    OPENAI_API_KEY: Required for embedding generation.
    OGREP_MODEL: Default embedding model (default: text-embedding-3-small).
    OGREP_DIMENSIONS: Default embedding dimensions.
"""

from __future__ import annotations

import argparse
import sys

from .commands import (
    cmd_benchmark,
    cmd_clean,
    cmd_index,
    cmd_models,
    cmd_query,
    cmd_reindex,
    cmd_reset,
    cmd_status,
    cmd_tune,
)
from .commands._common import add_scope_args
from .models import DEFAULT_MODEL

__version__ = "0.4.0"


def _add_model_args(parser: argparse.ArgumentParser, for_query: bool = False) -> None:
    """Add model-related arguments to a parser."""
    match_note = " (must match indexed model)" if for_query else ""
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        metavar="MODEL",
        help=f"Embedding model or alias: small, large, ada{match_note}. "
        f"Default: $OGREP_MODEL or {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--dimensions",
        "-d",
        type=int,
        default=None,
        metavar="DIM",
        help="Embedding dimensions. Default: $OGREP_DIMENSIONS or model default",
    )


def _build_parser() -> argparse.ArgumentParser:
    """
    Build and return the argument parser with all subcommands.

    Returns:
        Configured ArgumentParser with all ogrep subcommands.
    """
    p = argparse.ArgumentParser(
        prog="ogrep",
        description="Local semantic grep powered by SQLite and OpenAI embeddings",
        epilog="Run 'ogrep models' to see available embedding models.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="command")

    # index command
    p_index = sub.add_parser(
        "index",
        help="Index a directory for semantic search",
        description="Scan files, generate embeddings, and store in local SQLite database.",
    )
    p_index.add_argument("path", nargs="?", default=".", help="Root path (default: .)")
    add_scope_args(p_index)
    _add_model_args(p_index)
    p_index.add_argument(
        "--chunk-lines",
        type=int,
        default=None,
        help="Lines per chunk (default: model-specific, e.g., 60 for OpenAI, 90 for nomic, 30 for bge)",
    )
    p_index.add_argument(
        "--overlap",
        type=int,
        default=10,
        help="Overlapping lines between chunks (default: 10)",
    )
    p_index.add_argument(
        "--max-bytes",
        type=int,
        default=2_000_000,
        help="Max file size in bytes (default: 2MB)",
    )
    p_index.add_argument(
        "--exclude",
        "-e",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Additional exclude patterns (added to defaults)",
    )
    p_index.add_argument(
        "--include",
        "-i",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Include patterns (override default excludes). "
        "Example: -i '*.md' to index markdown files",
    )
    p_index.set_defaults(func=cmd_index)

    # query command
    p_query = sub.add_parser(
        "query",
        help="Semantic search against the index",
        description="Search indexed code by meaning using natural language queries.",
    )
    p_query.add_argument("query", help="Natural language search query")
    add_scope_args(p_query)
    p_query.add_argument(
        "--top",
        "-n",
        type=int,
        default=10,
        help="Number of results (default: 10)",
    )
    p_query.add_argument(
        "--refresh",
        "-r",
        action="store_true",
        help="Check for changed files and reindex before querying. "
        "Recommended for AI tools to ensure results reflect current code.",
    )
    _add_model_args(p_query, for_query=True)
    p_query.set_defaults(func=cmd_query)

    # reset command
    p_reset = sub.add_parser(
        "reset",
        help="Remove the index database",
        description="Delete the index database for the current scope.",
    )
    add_scope_args(p_reset)
    p_reset.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation prompt",
    )
    p_reset.set_defaults(func=cmd_reset)

    # reindex command
    p_reindex = sub.add_parser(
        "reindex",
        help="Force rebuild index from scratch",
        description="Remove existing index and rebuild completely.",
    )
    p_reindex.add_argument("path", nargs="?", default=".", help="Root path (default: .)")
    add_scope_args(p_reindex)
    _add_model_args(p_reindex)
    p_reindex.add_argument(
        "--chunk-lines",
        type=int,
        default=None,
        help="Lines per chunk (default: model-specific, e.g., 60 for OpenAI, 90 for nomic, 30 for bge)",
    )
    p_reindex.add_argument(
        "--overlap",
        type=int,
        default=10,
        help="Overlapping lines between chunks (default: 10)",
    )
    p_reindex.add_argument(
        "--max-bytes",
        type=int,
        default=2_000_000,
        help="Max file size in bytes",
    )
    p_reindex.add_argument(
        "--exclude",
        "-e",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Additional exclude patterns (added to defaults)",
    )
    p_reindex.add_argument(
        "--include",
        "-i",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Include patterns (override default excludes)",
    )
    p_reindex.set_defaults(func=cmd_reindex)

    # clean command
    p_clean = sub.add_parser(
        "clean",
        help="Remove stale entries from index",
        description="Remove entries for files that no longer exist.",
    )
    add_scope_args(p_clean)
    p_clean.add_argument(
        "--vacuum",
        action="store_true",
        help="Compact database after cleaning",
    )
    p_clean.set_defaults(func=cmd_clean)

    # status command
    p_status = sub.add_parser(
        "status",
        help="Show index status and statistics",
        description="Display index location, file count, chunk count, and model info.",
    )
    add_scope_args(p_status)
    p_status.set_defaults(func=cmd_status)

    # models command
    p_models = sub.add_parser(
        "models",
        help="List available embedding models",
        description="Show available OpenAI embedding models with pricing and use cases.",
    )
    p_models.set_defaults(func=cmd_models)

    # tune command
    p_tune = sub.add_parser(
        "tune",
        help="Auto-tune chunk size for optimal relevance",
        description="Test different chunk sizes and recommend optimal settings.",
    )
    p_tune.add_argument("path", nargs="?", default=".", help="Root path (default: .)")
    add_scope_args(p_tune)
    _add_model_args(p_tune)
    p_tune.add_argument(
        "--samples",
        "-s",
        type=int,
        default=5,
        help="Number of code patterns to test (default: 5)",
    )
    p_tune.add_argument(
        "--apply",
        "-a",
        action="store_true",
        help="Apply optimal settings and reindex",
    )
    p_tune.add_argument(
        "--save",
        action="store_true",
        help="Save optimal chunk size to .env file as OGREP_CHUNK_LINES",
    )
    p_tune.set_defaults(func=cmd_tune)

    # benchmark command
    p_bench = sub.add_parser(
        "benchmark",
        help="Compare all embedding models",
        description="Comprehensive benchmark comparing accuracy, speed, and optimal settings across all available models.",
    )
    p_bench.add_argument("path", nargs="?", default=".", help="Root path (default: .)")
    p_bench.add_argument(
        "--samples",
        "-s",
        type=int,
        default=10,
        help="Number of code patterns to test (default: 10)",
    )
    p_bench.add_argument(
        "--models",
        "-m",
        nargs="+",
        metavar="MODEL",
        help="Specific models to test (default: all available)",
    )
    p_bench.add_argument(
        "--local-only",
        action="store_true",
        help="Only test local models (via OGREP_BASE_URL)",
    )
    p_bench.add_argument(
        "--cloud-only",
        action="store_true",
        help="Only test cloud models (OpenAI)",
    )
    p_bench.add_argument(
        "--chunks",
        default="30,45,60,90,120",
        help="Chunk sizes to test (comma-separated, default: 30,45,60,90,120)",
    )
    p_bench.add_argument(
        "--overlaps",
        default="5,10,15,20",
        help="Overlap values to test (comma-separated, default: 5,10,15,20)",
    )
    p_bench.add_argument(
        "--save",
        action="store_true",
        help="Save optimal settings to .env file",
    )
    p_bench.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    p_bench.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed per-configuration results",
    )
    p_bench.set_defaults(func=cmd_benchmark)

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
