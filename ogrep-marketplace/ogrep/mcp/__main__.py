from __future__ import annotations

from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except Exception as e:
    raise SystemExit(
        "MCP extra not installed. Install with: pip install 'ogrep[mcp]'\n"
        f"Original import error: {e}"
    ) from e

from ogrep.indexer import index_path
from ogrep.search import query as query_db

mcp = FastMCP("ogrep")


@mcp.tool()
def ogrep_index(path: str = ".", db: str = ".ogrep/index.sqlite") -> dict:
    """Index a directory into a SQLite embeddings DB."""
    index_path(root=Path(path), db_path=Path(db))
    return {"status": "ok", "db": db, "path": path}


@mcp.tool()
def ogrep_search(q: str, db: str = ".ogrep/index.sqlite", top_k: int = 10) -> list[dict]:
    """Semantic search over the SQLite embeddings DB."""
    hits = query_db(db_path=Path(db), q=q, top_k=top_k)
    return [
        {
            "score": h.score,
            "path": h.path,
            "start_line": h.start_line,
            "end_line": h.end_line,
            "text": h.text,
        }
        for h in hits
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
