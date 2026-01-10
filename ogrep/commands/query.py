"""
Query command for ogrep.

Performs semantic search against an indexed codebase, returning
the most relevant code chunks ranked by cosine similarity.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..search import query as query_db
from ._common import resolve_db_path


def cmd_query(args: argparse.Namespace) -> int:
    """
    Run a semantic query against the index.

    Embeds the query text and searches for similar code chunks
    in the database using cosine similarity scoring.

    Args:
        args: Parsed command-line arguments containing:
            - query: Natural language search query
            - top: Number of results to return
            - db, profile, global_cache, repo_root: Scope options
            - model: OpenAI embedding model (must match indexed model)
            - dimensions: Embedding dimensions (must match indexed dimensions)

    Returns:
        Exit code (0 for success, 1 if database not found).
    """
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
