"""
Argument builder functions for CLI commands.

Extracts common argument patterns to reduce duplication between commands.
"""

from __future__ import annotations

import argparse

from ..models import DEFAULT_MODEL


def add_model_args(parser: argparse.ArgumentParser, for_query: bool = False) -> None:
    """
    Add embedding model arguments to a parser.

    Args:
        parser: ArgumentParser to add arguments to.
        for_query: If True, adds note about matching indexed model.
    """
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


def add_indexing_args(parser: argparse.ArgumentParser) -> None:
    """
    Add common indexing arguments shared by index and reindex commands.

    Args:
        parser: ArgumentParser to add arguments to.
    """
    parser.add_argument(
        "--chunk-lines",
        type=int,
        default=None,
        help="Lines per chunk (default: model-specific, e.g., 60 for OpenAI, 30 for nomic/bge)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=None,
        help="Overlapping lines between chunks (default: model-specific, e.g., 15 for nomic, 5 for bge)",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=2_000_000,
        help="Max file size in bytes (default: 2MB)",
    )
    parser.add_argument(
        "--exclude",
        "-e",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Additional exclude patterns (added to defaults)",
    )
    parser.add_argument(
        "--include",
        "-i",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Include patterns (override default excludes). "
        "Example: -i '*.md' to index markdown files",
    )
    parser.add_argument(
        "--ast",
        action="store_true",
        help="Use AST-aware chunking for semantic boundaries. "
        "Chunks by function/class instead of lines. "
        "Requires: pip install 'ogrep[ast]'",
    )


def add_benchmark_args(parser: argparse.ArgumentParser) -> None:
    """
    Add benchmark-specific arguments.

    Args:
        parser: ArgumentParser to add arguments to.
    """
    parser.add_argument(
        "--samples",
        "-s",
        type=int,
        default=10,
        help="Number of code patterns to test (default: 10)",
    )
    parser.add_argument(
        "--models",
        "-m",
        nargs="+",
        metavar="MODEL",
        help="Specific models to test (default: all available)",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Only test local models (via OGREP_BASE_URL)",
    )
    parser.add_argument(
        "--cloud-only",
        action="store_true",
        help="Only test cloud models (OpenAI)",
    )
    parser.add_argument(
        "--chunks",
        default="30,60,90",
        help="Chunk sizes to test (comma-separated, default: 30,60,90)",
    )
    parser.add_argument(
        "--overlaps",
        default="5,10,15",
        help="Overlap values to test (comma-separated, default: 5,10,15)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save optimal settings to .env file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed per-configuration results",
    )
