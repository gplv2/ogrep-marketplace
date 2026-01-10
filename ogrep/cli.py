from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from .indexer import index_path
from .search import query as query_db


def _repo_hash(root: Path) -> str:
    """Generate a short hash from repo path for global cache keying."""
    return hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12]


def resolve_db_path(
    db_arg: str | None,
    profile: str | None,
    global_cache: bool,
    repo_root: Path | None = None,
) -> Path:
    """
    Resolve the database path based on scope flags.

    Priority:
    1. Explicit --db path
    2. --global-cache: ~/.cache/ogrep/<repo_hash>/index.sqlite
    3. --profile: .ogrep/<profile>/index.sqlite
    4. Default: .ogrep/index.sqlite
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
    """Add common scope/fencing arguments to a parser."""
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


def cmd_index(args: argparse.Namespace) -> int:
    """Index a directory."""
    root = Path(args.path).resolve()
    repo_root = args.repo_root.resolve() if args.repo_root else root
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    index_path(
        root=root,
        db_path=db,
        model=args.model,
        dimensions=args.dimensions,
        chunk_lines=args.chunk_lines,
        overlap=args.overlap,
        max_bytes=args.max_bytes,
    )
    print(f"Indexed into {db}")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Run a semantic query."""
    repo_root = args.repo_root.resolve() if args.repo_root else Path.cwd()
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    if not db.exists():
        print(f"Error: Database not found at {db}", file=sys.stderr)
        print("Run 'ogrep index .' first to create the index.", file=sys.stderr)
        return 1

    hits = query_db(
        db_path=db,
        q=args.query,
        top_k=args.top,
        model=args.model,
        dimensions=args.dimensions,
    )
    for h in hits:
        print(f"{h.path}:{h.start_line}-{h.end_line}  score={h.score:0.4f}")
        snippet = h.text.strip().replace("\n", "\\n")
        print(f"  {snippet[:240]}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    """Remove the index database for the current scope."""
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


def cmd_reindex(args: argparse.Namespace) -> int:
    """Force rebuild: remove existing index and reindex from scratch."""
    root = Path(args.path).resolve()
    repo_root = args.repo_root.resolve() if args.repo_root else root
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    # Remove existing database
    if db.exists():
        db.unlink()
        print(f"Removed existing index at {db}")

    # Reindex
    index_path(
        root=root,
        db_path=db,
        model=args.model,
        dimensions=args.dimensions,
        chunk_lines=args.chunk_lines,
        overlap=args.overlap,
        max_bytes=args.max_bytes,
    )
    print(f"Reindexed into {db}")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Remove stale entries (files that no longer exist) and optionally vacuum."""
    import sqlite3

    repo_root = args.repo_root.resolve() if args.repo_root else Path.cwd()
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    if not db.exists():
        print(f"No database found at {db}")
        return 0

    con = sqlite3.connect(str(db))
    cur = con.cursor()

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

    con.close()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show index status and statistics."""
    import sqlite3

    repo_root = args.repo_root.resolve() if args.repo_root else Path.cwd()
    db = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)

    print(f"Database: {db}")

    if not db.exists():
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
    model = row[0] if row else "N/A"
    dim = row[1] if row else "N/A"

    # Get DB file size
    db_size = db.stat().st_size
    if db_size >= 1024 * 1024:
        size_str = f"{db_size / (1024 * 1024):.1f} MB"
    elif db_size >= 1024:
        size_str = f"{db_size / 1024:.1f} KB"
    else:
        size_str = f"{db_size} bytes"

    print("Status: Indexed")
    print(f"Files: {file_count}")
    print(f"Chunks: {chunk_count}")
    print(f"Model: {model}")
    print(f"Dimensions: {dim}")
    print(f"Size: {size_str}")

    con.close()
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        prog="ogrep",
        description="Local semantic grep (SQLite + OpenAI embeddings)",
    )
    p.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    sub = p.add_subparsers(dest="cmd", required=True)

    # index command
    p_i = sub.add_parser("index", help="Index a directory")
    p_i.add_argument("path", nargs="?", default=".", help="Root path (default: .)")
    add_scope_args(p_i)
    p_i.add_argument("--model", default="text-embedding-3-small")
    p_i.add_argument("--dimensions", type=int, default=None)
    p_i.add_argument("--chunk-lines", type=int, default=120)
    p_i.add_argument("--overlap", type=int, default=20)
    p_i.add_argument("--max-bytes", type=int, default=2_000_000)
    p_i.set_defaults(func=cmd_index)

    # query command
    p_q = sub.add_parser("query", help="Semantic query")
    p_q.add_argument("query", help="Query text")
    add_scope_args(p_q)
    p_q.add_argument("--top", type=int, default=10)
    p_q.add_argument("--model", default="text-embedding-3-small")
    p_q.add_argument("--dimensions", type=int, default=None)
    p_q.set_defaults(func=cmd_query)

    # reset command
    p_r = sub.add_parser("reset", help="Remove the index database")
    add_scope_args(p_r)
    p_r.add_argument("--force", "-f", action="store_true", help="Skip confirmation")
    p_r.set_defaults(func=cmd_reset)

    # reindex command
    p_ri = sub.add_parser("reindex", help="Force rebuild index from scratch")
    p_ri.add_argument("path", nargs="?", default=".", help="Root path (default: .)")
    add_scope_args(p_ri)
    p_ri.add_argument("--model", default="text-embedding-3-small")
    p_ri.add_argument("--dimensions", type=int, default=None)
    p_ri.add_argument("--chunk-lines", type=int, default=120)
    p_ri.add_argument("--overlap", type=int, default=20)
    p_ri.add_argument("--max-bytes", type=int, default=2_000_000)
    p_ri.set_defaults(func=cmd_reindex)

    # clean command
    p_c = sub.add_parser("clean", help="Remove stale entries from index")
    add_scope_args(p_c)
    p_c.add_argument("--vacuum", action="store_true", help="Compact database after cleaning")
    p_c.set_defaults(func=cmd_clean)

    # status command
    p_s = sub.add_parser("status", help="Show index status and statistics")
    add_scope_args(p_s)
    p_s.set_defaults(func=cmd_status)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
