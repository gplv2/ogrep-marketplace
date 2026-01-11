"""
Index command for ogrep.

Indexes a directory by scanning files, chunking text, and storing
embeddings in a local SQLite database for semantic search.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..indexer import IndexStats, index_path, iter_files, load_ogrepignore
from ..models import get_optimal_chunk_lines
from ._common import require_embedding_config, resolve_db_path


def _format_size(size: int) -> str:
    """Format file size in human-readable form."""
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    else:
        return f"{size / (1024 * 1024):.1f}MB"


def _list_files(root: Path, exclude: list[str], include: list[str]) -> int:
    """
    List files that would be indexed, sorted by extension then size.

    Args:
        root: Root directory to scan.
        exclude: Additional exclude patterns.
        include: Include patterns (override excludes).

    Returns:
        Exit code (0 for success).
    """
    # Load .ogrepignore patterns
    ignore_patterns = load_ogrepignore(root)
    all_exclude = list(exclude) + ignore_patterns

    # Collect files with their stats
    file_info: list[tuple[Path, str, int]] = []  # (path, extension, size)

    for p in iter_files(root, exclude=all_exclude, include=include):
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
            ext = p.suffix.lower() if p.suffix else "(no extension)"
            file_info.append((p, ext, size))
        except (OSError, FileNotFoundError):
            continue

    if not file_info:
        print("No files would be indexed.")
        return 0

    # Sort by extension, then by size (ascending, so biggest last)
    file_info.sort(key=lambda x: (x[1], x[2]))

    # Group by extension for summary
    ext_stats: dict[str, tuple[int, int]] = {}  # ext -> (count, total_size)
    for _, ext, size in file_info:
        if ext not in ext_stats:
            ext_stats[ext] = (0, 0)
        count, total = ext_stats[ext]
        ext_stats[ext] = (count + 1, total + size)

    # Print file list
    current_ext = None
    for p, ext, size in file_info:
        if ext != current_ext:
            current_ext = ext
            ext_count, ext_total = ext_stats[ext]
            print(f"\n── {ext} ({ext_count} files, {_format_size(ext_total)}) ──")
        rel_path = p.relative_to(root) if p.is_relative_to(root) else p
        print(f"  {_format_size(size):>8}  {rel_path}")

    # Print summary
    total_files = len(file_info)
    total_size = sum(size for _, _, size in file_info)
    print(f"\n{'─' * 40}")
    print(f"Total: {total_files} files, {_format_size(total_size)}")
    print(f"Extensions: {len(ext_stats)}")

    # Show top 5 largest files
    largest = sorted(file_info, key=lambda x: x[2], reverse=True)[:5]
    if largest:
        print("\nLargest files:")
        for p, _ext, size in largest:
            rel_path = p.relative_to(root) if p.is_relative_to(root) else p
            print(f"  {_format_size(size):>8}  {rel_path}")

    return 0


def _resolve_chunk_lines(args: argparse.Namespace) -> int:
    """
    Resolve chunk size from args or model-specific default.

    Args:
        args: Parsed command-line arguments with chunk_lines and model.

    Returns:
        Chunk size in lines.
    """
    if args.chunk_lines is not None:
        return args.chunk_lines
    return get_optimal_chunk_lines(args.model)


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """
    Resolve root directory and database path from arguments.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Tuple of (root_path, db_path).
    """
    root = Path(args.path).resolve()
    repo_root = args.repo_root.resolve() if args.repo_root else root
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)
    return root, db


def _print_stats(db: Path, stats: IndexStats) -> None:
    """
    Print indexing statistics to stdout.

    Args:
        db: Path to the database file.
        stats: IndexStats dataclass with indexing results.
    """
    print(f"Indexed into {db}")
    print(f"  Files: {stats.files_indexed} indexed, {stats.files_skipped} skipped")

    if stats.chunks_total > 0:
        _print_chunk_stats(stats)


def _print_chunk_stats(stats: IndexStats) -> None:
    """
    Print chunk-level statistics.

    Args:
        stats: IndexStats dataclass with chunk counts.
    """
    msg = f"  Chunks: {stats.chunks_total} total"

    if stats.chunks_reused > 0:
        msg += f" ({stats.chunks_reused} reused, ~{stats.tokens_saved_estimate} tokens saved)"
    else:
        msg += f" ({stats.chunks_embedded} embedded)"

    print(msg)


def cmd_index(args: argparse.Namespace) -> int:
    """
    Index a directory for semantic search.

    Scans the target directory for text files, splits them into chunks,
    generates embeddings via OpenAI API, and stores everything in a
    local SQLite database.

    Args:
        args: Parsed command-line arguments containing:
            - path: Directory to index (default: current directory)
            - db, profile, global_cache, repo_root: Scope options
            - model: OpenAI embedding model name
            - dimensions: Embedding dimensions (model-specific)
            - chunk_lines: Lines per chunk (None = model-specific default)
            - overlap: Overlapping lines between chunks
            - max_bytes: Maximum file size to index
            - exclude: Additional glob patterns to exclude
            - include: Glob patterns to include (override excludes)
            - list: If True, list files that would be indexed (dry run)

    Returns:
        Exit code (0 for success, 1 for configuration error).
    """
    root = Path(args.path).resolve()

    # Handle --list flag (doesn't require embedding config)
    if getattr(args, "list", False):
        return _list_files(root, args.exclude, args.include)

    if not require_embedding_config():
        return 1

    root, db = _resolve_paths(args)
    chunk_lines = _resolve_chunk_lines(args)

    stats = index_path(
        root=root,
        db_path=db,
        model=args.model,
        dimensions=args.dimensions,
        chunk_lines=chunk_lines,
        overlap=args.overlap,
        max_bytes=args.max_bytes,
        exclude=args.exclude,
        include=args.include,
    )

    _print_stats(db, stats)
    return 0
