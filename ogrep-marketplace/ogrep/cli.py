from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .indexer import index_path
from .search import query as query_db


def default_db() -> Path:
    return Path(".ogrep/index.sqlite")


def cmd_index(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve()
    db = Path(args.db)

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
    db = Path(args.db)
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


def main() -> None:
    p = argparse.ArgumentParser(prog="ogrep", description="Local semantic grep (SQLite + OpenAI embeddings)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_i = sub.add_parser("index", help="Index a directory")
    p_i.add_argument("path", nargs="?", default=".", help="Root path (default: .)")
    p_i.add_argument("--db", default=str(default_db()), help="SQLite DB path (default: .ogrep/index.sqlite)")
    p_i.add_argument("--model", default="text-embedding-3-small")
    p_i.add_argument("--dimensions", type=int, default=None)
    p_i.add_argument("--chunk-lines", type=int, default=120)
    p_i.add_argument("--overlap", type=int, default=20)
    p_i.add_argument("--max-bytes", type=int, default=2_000_000)
    p_i.set_defaults(func=cmd_index)

    p_q = sub.add_parser("query", help="Semantic query")
    p_q.add_argument("query", help="Query text")
    p_q.add_argument("--db", default=str(default_db()), help="SQLite DB path (default: .ogrep/index.sqlite)")
    p_q.add_argument("--top", type=int, default=10)
    p_q.add_argument("--model", default="text-embedding-3-small")
    p_q.add_argument("--dimensions", type=int, default=None)
    p_q.set_defaults(func=cmd_query)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
