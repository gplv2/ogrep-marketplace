"""
Command-line interface for ogrep.

Semantic grep for codebases — search by meaning, not just keywords.
Supports hybrid (semantic + keyword), pure semantic, or FTS5 fulltext modes.

Usage:
    ogrep index .                           # Index current directory
    ogrep query "search text"               # Search (hybrid mode)
    ogrep query "text" --mode semantic      # Pure semantic search
    ogrep query "text" --mode fulltext      # Keyword search (FTS5)
    ogrep query "text" --json               # JSON output for AI tools
    ogrep chunk "path:N" -C 1               # Get chunk with context
    ogrep status                            # Show index statistics
    ogrep reset --force                     # Delete index
    ogrep reindex .                         # Rebuild (enables FTS5)
    ogrep clean --vacuum                    # Remove stale entries
    ogrep models                            # List available models
    ogrep tune .                            # Auto-tune chunk size
    ogrep benchmark .                       # Compare all models

Search Modes:
    hybrid   - Combines semantic + keyword (default, best for most queries)
    semantic - Embeddings only (conceptual questions)
    fulltext - FTS5 keywords (exact identifiers)

Environment Variables:
    OPENAI_API_KEY: Required for OpenAI embeddings.
    OGREP_BASE_URL: Local server URL (e.g., LM Studio).
    OGREP_MODEL: Default embedding model.
    OGREP_SEARCH_MODE: Default search mode (hybrid/semantic/fulltext).
    OGREP_HYBRID_ALPHA: Semantic weight in hybrid mode (0.0-1.0).
"""

from __future__ import annotations

import argparse
import sys

from .commands import (
    cmd_benchmark,
    cmd_chunk,
    cmd_clean,
    cmd_health,
    cmd_index,
    cmd_models,
    cmd_query,
    cmd_reindex,
    cmd_reset,
    cmd_status,
    cmd_tune,
)
from .commands._arg_builders import add_benchmark_args, add_indexing_args, add_model_args
from .commands._common import add_scope_args

__version__ = "0.5.0"


def _build_parser() -> argparse.ArgumentParser:
    """
    Build and return the argument parser with all subcommands.

    Returns:
        Configured ArgumentParser with all ogrep subcommands.
    """
    p = argparse.ArgumentParser(
        prog="ogrep",
        description="Semantic grep for codebases. Search by meaning, not just keywords. "
        "Supports hybrid (semantic + keyword), pure semantic, or FTS5 fulltext modes.",
        epilog="Search modes: --mode hybrid (default), semantic, fulltext. "
        "Run 'ogrep models' to see embedding models. "
        "Use --json for AI tool integration.",
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
    add_model_args(p_index)
    add_indexing_args(p_index)
    p_index.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List files that would be indexed (sorted by extension, biggest last). "
        "Does not actually index.",
    )
    p_index.add_argument(
        "--no-detect",
        action="store_true",
        help="Disable file type detection (use fast null-byte check only). "
        "By default, uses 'file' command for accurate MIME type detection.",
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
    p_query.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (full text, structured metadata). "
        "Recommended for AI tools and programmatic use.",
    )
    p_query.add_argument(
        "--mode",
        "-M",
        choices=["semantic", "fulltext", "hybrid"],
        default=None,
        help="Search mode: semantic (embeddings only), fulltext (FTS5 keywords), "
        "hybrid (combined, default). Uses OGREP_SEARCH_MODE env var if not specified.",
    )
    add_model_args(p_query, for_query=True)
    p_query.set_defaults(func=cmd_query)

    # chunk command
    p_chunk = sub.add_parser(
        "chunk",
        help="Get a chunk by reference with optional context",
        description="Retrieve chunks by path:index reference or raw ID. "
        "Useful for expanding context after query finds something interesting.",
    )
    p_chunk.add_argument(
        "ref",
        help="Chunk reference: 'path/file.py:N' (path:chunk_index) or raw chunk ID",
    )
    add_scope_args(p_chunk)
    p_chunk.add_argument(
        "--before",
        "-B",
        type=int,
        default=0,
        metavar="N",
        help="Include N chunks before the requested chunk",
    )
    p_chunk.add_argument(
        "--after",
        "-A",
        type=int,
        default=0,
        metavar="N",
        help="Include N chunks after the requested chunk",
    )
    p_chunk.add_argument(
        "--context",
        "-C",
        type=int,
        default=0,
        metavar="N",
        help="Include N chunks before AND after (shorthand for -B N -A N)",
    )
    p_chunk.set_defaults(func=cmd_chunk)

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
    add_model_args(p_reindex)
    add_indexing_args(p_reindex)
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

    # health command
    p_health = sub.add_parser(
        "health",
        help="Show database health and diagnostics",
        description="Display comprehensive database diagnostics including table sizes, "
        "indexes, SQLite info, FTS5 stats, and integrity checks. "
        "Supports repair operations via flags.",
    )
    add_scope_args(p_health)
    p_health.add_argument(
        "--vacuum",
        action="store_true",
        help="Run VACUUM to reclaim space and defragment database",
    )
    p_health.add_argument(
        "--rebuild-fts",
        action="store_true",
        help="Drop and rebuild FTS5 index from chunks table",
    )
    p_health.add_argument(
        "--reindex",
        action="store_true",
        help="Show reindex command (does not run automatically - requires re-embedding)",
    )
    p_health.add_argument(
        "--integrity",
        action="store_true",
        help="Run full PRAGMA integrity_check (slow on large databases)",
    )
    p_health.add_argument(
        "--full",
        action="store_true",
        help="Run vacuum + rebuild-fts + integrity (not reindex)",
    )
    p_health.set_defaults(func=cmd_health)

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
    add_model_args(p_tune)
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
    add_benchmark_args(p_bench)
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
