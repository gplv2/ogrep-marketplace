"""
MCP server for ogrep — semantic code search.

Exposes ogrep's SQLite-based search, indexing, and diagnostics as MCP tools.
Runs as a persistent process, keeping models warm in memory for fast reranking.

Usage:
    python -m ogrep.mcp          # stdio transport (default for Claude Code)

Prerequisites:
    pip install 'ogrep[mcp]'     # MCP protocol support
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

# Load .env from cwd so API keys are available when Claude Code spawns the MCP
# child process. python-dotenv is a core ogrep dependency, so always available.
# override=False means explicit env vars (from shell, Claude settings, or
# plugin.json "env") always win over .env file values.
from dotenv import load_dotenv

load_dotenv(Path.cwd() / ".env", override=False)

try:
    from mcp.server.fastmcp import FastMCP
except Exception as e:
    raise SystemExit(
        "MCP extra not installed. Install with: pip install 'ogrep[mcp]'\n"
        f"Original import error: {e}"
    ) from e

from ..commands._common import (  # noqa: E402
    detect_language,
    find_git_root,
    get_current_branch,
    resolve_db_path,
)
from ..db import connect, get_branch_file_counts  # noqa: E402
from ..indexer import index_path as _index_path  # noqa: E402
from ..search import Hit, PathFilter, filter_hits_by_path  # noqa: E402
from ..search import query as _query_db  # noqa: E402

mcp = FastMCP("ogrep")

_log = logging.getLogger("ogrep.mcp")

# ---------------------------------------------------------------------------
# Background refresh
# ---------------------------------------------------------------------------

# Repos seen by any tool call — the refresh thread indexes all of them.
_known_repos: dict[Path, Path] = {}  # repo_root -> db_path
_known_repos_lock = threading.Lock()


def _register_repo(repo_root: Path, db_path: Path) -> None:
    """Record a repo so the background thread can refresh it."""
    with _known_repos_lock:
        _known_repos[repo_root] = db_path


def _refresh_loop(interval: int) -> None:
    """Periodically run incremental index on all known repos."""
    while True:
        time.sleep(interval)
        with _known_repos_lock:
            repos = dict(_known_repos)
        for repo_root, db_path in repos.items():
            if not db_path.exists():
                continue
            try:
                con = sqlite3.connect(str(db_path))
                row = con.execute("SELECT model, dim FROM chunks LIMIT 1").fetchone()
                con.close()
                if not row:
                    continue
                model, dim = row[0], row[1]
                stats = _index_path(
                    root=repo_root,
                    db_path=db_path,
                    model=model,
                    dimensions=dim,
                )
                if stats.files_indexed > 0:
                    _log.info(
                        "background refresh: %s — %d files indexed",
                        repo_root.name,
                        stats.files_indexed,
                    )
            except Exception:
                _log.debug("background refresh failed for %s", repo_root, exc_info=True)


def _start_refresh_thread() -> None:
    """Start background refresh if OGREP_REFRESH_INTERVAL is set."""
    raw = os.environ.get("OGREP_REFRESH_INTERVAL", "0")
    try:
        interval = int(raw)
    except ValueError:
        return
    if interval <= 0:
        return
    t = threading.Thread(target=_refresh_loop, args=(interval,), daemon=True)
    t.start()
    _log.info("background refresh enabled: every %ds", interval)


_start_refresh_thread()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_context(path: str = ".") -> tuple[Path, Path]:
    """Resolve repo root and DB path from a directory.

    Uses git root detection so .ogrep/ is always at the repo root.
    Also registers the repo for background refresh.

    Returns:
        (repo_root, db_path)
    """
    target = Path(path).resolve()
    git_root = find_git_root(target)
    repo_root = git_root if git_root else target
    db_path = resolve_db_path(None, None, False, repo_root)

    # Load .env from the resolved repo root (may differ from cwd at startup)
    load_dotenv(repo_root / ".env", override=False)

    _register_repo(repo_root, db_path)

    return repo_root, db_path


def _get_index_info(db_path: Path) -> tuple[str, int] | None:
    """Read model/dimensions from an existing index."""
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute("SELECT model, dim FROM chunks LIMIT 1").fetchone()
        return (row[0], row[1]) if row else None
    finally:
        con.close()


def _hit_to_dict(hit: Hit, repo_root: Path, rank: int) -> dict:
    """Convert a Hit to a serialisable dictionary."""
    try:
        rel_path = str(Path(hit.path).relative_to(repo_root))
    except ValueError:
        rel_path = hit.path

    confidence = (
        hit.confidence_details.to_dict()
        if hit.confidence_details is not None
        else hit.confidence
    )

    return {
        "rank": rank,
        "chunk_ref": f"{rel_path}:{hit.chunk_index}",
        "chunk_id": hit.chunk_id,
        "path": hit.path,
        "relative_path": rel_path,
        "start_line": hit.start_line,
        "end_line": hit.end_line,
        "score": round(hit.score, 4),
        "confidence": confidence,
        "language": detect_language(hit.path),
        "text": hit.text,
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def ogrep_query(
    query: str,
    path: str = ".",
    top_k: int = 10,
    mode: str = "hybrid",
    branch: str | None = None,
    glob: str | None = None,
    exclude: str | None = None,
    summarize: bool = False,
    rerank: bool = False,
    rerank_model: str | None = None,
    refresh: bool = True,
) -> dict:
    """Search the ogrep index using semantic, fulltext, or hybrid search.

    Returns ranked code chunks with scores and confidence levels.
    Use summarize=True for a token-efficient file-level overview.

    If the directory is not indexed, returns an error dict with an
    "error" key — do not retry, fall back to grep/glob or offer to
    run ogrep_index first.

    Reranking guidance: reranking improves results with local/weak
    embeddings (nomic, bge, minilm) but DEGRADES quality with strong
    API embeddings (voyage-code-3, voyage-3, text-embedding-3-small/large).
    When in doubt, leave rerank=False — the default hybrid search with
    a quality embedder is already well-calibrated.

    Args:
        query: Natural language search query (min 2 chars).
        path: Directory to search in (resolves repo root automatically).
        top_k: Number of results to return.
        mode: Search mode — "hybrid" (default), "semantic", or "fulltext".
        branch: Git branch to search (auto-detected if omitted).
        glob: Glob pattern to include (e.g. "*.py", "src/**/*.ts").
        exclude: Glob pattern to exclude (e.g. "tests/*").
        summarize: If True, aggregate results to file-level summary.
        rerank: If True, apply cross-encoder reranking. Only beneficial with
            local/weak embeddings (nomic, bge). Degrades results with strong
            models (voyage-*, text-embedding-3-*). Default False.
        rerank_model: Override reranking model (flashrank, voyage, minilm,
            bge-m3). Requires rerank=True. flashrank is lightweight (ONNX);
            bge-m3 is heavy and slow without GPU.
        refresh: If True (default), auto-reindex changed files before searching.
    """
    repo_root, db_path = _resolve_context(path)

    if not db_path.exists():
        return {"error": f"No ogrep index found. Run: ogrep index {path}"}

    # Read model/dims from the index
    index_info = _get_index_info(db_path)
    if not index_info:
        return {"error": "Index is empty — no chunks found."}
    index_model, index_dim = index_info

    # Resolve branch
    search_branch = branch or get_current_branch(repo_root)

    # Auto-refresh: run incremental index before querying.
    # Always call _index_path (not just on stale files) so NEW files
    # that were never indexed also get picked up.  index_path is
    # already incremental — unchanged files are skipped cheaply.
    refreshed_files = 0
    if refresh:
        stats = _index_path(
            root=repo_root,
            db_path=db_path,
            model=index_model,
            dimensions=index_dim,
        )
        refreshed_files = stats.files_indexed

    # Over-fetch when filtering or reranking
    fetch_limit = top_k
    path_filter = PathFilter(
        glob_patterns=[glob] if glob else None,
        exclude_patterns=[exclude] if exclude else None,
    )
    has_filter = not path_filter.is_empty()

    if rerank:
        from ..rerank import DEFAULT_RERANK_TOPN

        fetch_limit = max(top_k, DEFAULT_RERANK_TOPN)
    if has_filter:
        fetch_limit = max(fetch_limit, top_k * 3)

    # Run search
    hits, fts_available = _query_db(
        db_path=db_path,
        q=query,
        top_k=fetch_limit,
        model=index_model,
        dimensions=index_dim,
        mode=mode,
        branch=search_branch,
    )

    # Rerank
    reranked = False
    if rerank and hits:
        try:
            from ..rerank import is_reranker_available, rerank_results

            if is_reranker_available(rerank_model):
                from ..cache import get_cache_path

                hits = rerank_results(
                    query,
                    hits,
                    top_n=fetch_limit,
                    model_name=rerank_model,
                    cache_path=get_cache_path(db_path),
                )
                hits = hits[:top_k]
                reranked = True
        except Exception:
            pass  # Fall back to unreranked results

    # Path filter
    filter_stats = None
    if has_filter:
        hits, filter_stats = filter_hits_by_path(hits, path_filter, top_k)
        hits = hits[:top_k]

    # Build output
    stats: dict = {
        "total_results": len(hits),
        "search_mode": mode,
        "reranked": reranked,
        "fts_available": fts_available,
        "index_model": index_model,
        "index_dimensions": index_dim,
        "branch": search_branch,
        "refreshed_files": refreshed_files,
    }
    if filter_stats is not None:
        stats["path_filter"] = filter_stats.to_dict()

    if summarize:
        from ..commands.query import _aggregate_to_summary

        file_summaries = _aggregate_to_summary(hits, repo_root)
        return {
            "query": query,
            "mode": mode,
            "summary": True,
            "total_chunks_matched": len(hits),
            "files": file_summaries,
            "stats": stats,
        }

    results = [_hit_to_dict(h, repo_root, rank) for rank, h in enumerate(hits, 1)]
    return {
        "query": query,
        "results": results,
        "stats": stats,
    }


@mcp.tool()
def ogrep_chunk(
    ref: str,
    path: str = ".",
    context: int = 0,
    before: int = 0,
    after: int = 0,
) -> dict:
    """Expand a chunk reference with surrounding context.

    Use after ogrep_query to read more code around an interesting result.
    If the directory is not indexed, returns an error dict — do not retry.

    Args:
        ref: Chunk reference — "path/file.py:N" (path:chunk_index) or raw chunk ID.
        path: Directory to resolve repo root from.
        context: Number of chunks before AND after (shorthand for before+after).
        before: Number of chunks to include before the target.
        after: Number of chunks to include after the target.
    """
    from ..commands.chunk import _chunk_to_dict, _parse_chunk_ref

    repo_root, db_path = _resolve_context(path)

    if not db_path.exists():
        return {"error": f"No ogrep index found. Run: ogrep index {path}"}

    rel_path, chunk_index, chunk_id = _parse_chunk_ref(ref)

    before_count = max(before, context)
    after_count = max(after, context)

    con = sqlite3.connect(str(db_path))
    try:
        # Find the target chunk
        if chunk_id is not None:
            row = con.execute(
                "SELECT c.id, c.chunk_index, f.path, c.start_line, c.end_line, c.text "
                "FROM chunks c JOIN files f ON f.id = c.file_id WHERE c.id = ?",
                (chunk_id,),
            ).fetchone()
        elif rel_path and chunk_index is not None:
            row = con.execute(
                "SELECT c.id, c.chunk_index, f.path, c.start_line, c.end_line, c.text "
                "FROM chunks c JOIN files f ON f.id = c.file_id "
                "WHERE c.chunk_index = ? AND (f.path LIKE ? OR f.path = ?)",
                (chunk_index, f"%/{rel_path}", str(repo_root / rel_path)),
            ).fetchone()
        else:
            return {"error": f"Invalid chunk reference: {ref}. Use 'path/file.py:N' or raw ID."}

        if row is None:
            return {"error": f"Chunk not found: {ref}"}

        requested = _chunk_to_dict(row, repo_root)
        file_path = row[2]
        file_chunk_index = row[1]

        before_chunks = []
        after_chunks = []

        if before_count > 0:
            before_rows = con.execute(
                "SELECT c.id, c.chunk_index, f.path, c.start_line, c.end_line, c.text "
                "FROM chunks c JOIN files f ON f.id = c.file_id "
                "WHERE f.path = ? AND c.chunk_index < ? "
                "ORDER BY c.chunk_index DESC LIMIT ?",
                (file_path, file_chunk_index, before_count),
            ).fetchall()
            before_chunks = [_chunk_to_dict(r, repo_root) for r in reversed(before_rows)]

        if after_count > 0:
            after_rows = con.execute(
                "SELECT c.id, c.chunk_index, f.path, c.start_line, c.end_line, c.text "
                "FROM chunks c JOIN files f ON f.id = c.file_id "
                "WHERE f.path = ? AND c.chunk_index > ? "
                "ORDER BY c.chunk_index ASC LIMIT ?",
                (file_path, file_chunk_index, after_count),
            ).fetchall()
            after_chunks = [_chunk_to_dict(r, repo_root) for r in after_rows]
    finally:
        con.close()

    return {
        "requested": requested,
        "before": before_chunks,
        "after": after_chunks,
    }


@mcp.tool()
def ogrep_index(
    path: str = ".",
    no_ast: bool = False,
) -> dict:
    """Index a directory for semantic search.

    Incremental — only embeds new or changed files, skips unchanged ones.
    Safe to call repeatedly; it creates the index if missing or updates it
    if files have changed.

    The embedding model is auto-selected based on available API keys
    (VOYAGE_API_KEY → voyage-code-3, OPENAI_API_KEY → text-embedding-3-small,
    else local nomic). The model choice affects whether reranking helps —
    see ogrep_query docstring.

    Args:
        path: Directory to index.
        no_ast: If True, use line-based chunking instead of AST-aware chunking.
    """
    repo_root, db_path = _resolve_context(path)

    stats = _index_path(
        root=repo_root,
        db_path=db_path,
        ast=not no_ast,
        branch=get_current_branch(repo_root),
    )

    return {
        "status": "ok",
        "files_scanned": stats.files_scanned,
        "files_indexed": stats.files_indexed,
        "files_skipped": stats.files_skipped,
        "chunks_total": stats.chunks_total,
        "chunks_embedded": stats.chunks_embedded,
        "chunks_reused": stats.chunks_reused,
        "tokens_saved_estimate": stats.tokens_saved_estimate,
        "branch": stats.branch,
        "model": stats.model,
        "ast_mode": stats.ast_mode,
    }


@mcp.tool()
def ogrep_status(path: str = ".") -> dict:
    """Show index statistics — files, chunks, model, branch info.

    Returns the embedding model used for the index in the "model" field.
    Use this to decide whether reranking is appropriate in ogrep_query:
    strong models (voyage-*, text-embedding-3-*) do NOT benefit from
    reranking; local models (nomic, bge, minilm) do.

    If not indexed, returns {"indexed": false, "status": "not_indexed"}.

    Args:
        path: Directory to check.
    """
    repo_root, db_path = _resolve_context(path)

    if not db_path.exists():
        return {
            "database": str(db_path),
            "indexed": False,
            "status": "not_indexed",
        }

    current_branch = get_current_branch(repo_root)
    con = connect(db_path, init_fts=False)
    try:
        cur = con.cursor()
        branch_counts = get_branch_file_counts(con)

        cur.execute("SELECT COUNT(*) FROM files")
        file_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cur.fetchone()[0]

        cur.execute("SELECT model, dim FROM chunks LIMIT 1")
        row = cur.fetchone()
        model = row[0] if row else None
        dim = row[1] if row else None

        # AST mode
        ast_mode = None
        try:
            ast_row = cur.execute(
                "SELECT value FROM index_metadata WHERE key = 'ast_mode'"
            ).fetchone()
            if ast_row:
                ast_mode = ast_row[0] == "true"
        except sqlite3.OperationalError:
            pass

        size_bytes = db_path.stat().st_size
    finally:
        con.close()

    result: dict = {
        "database": str(db_path),
        "indexed": True,
        "status": "indexed",
        "branch": current_branch,
        "branch_files": branch_counts.get(current_branch, 0),
        "total_files": file_count,
        "branches": branch_counts,
        "chunks": chunk_count,
        "model": model,
        "dimensions": dim,
        "size_bytes": size_bytes,
    }
    if ast_mode is not None:
        result["ast_mode"] = ast_mode
    return result


@mcp.tool()
def ogrep_health(path: str = ".") -> dict:
    """Database diagnostics — table stats, FTS5 info, integrity check.

    Read-only health check. For repairs use the CLI: ogrep health --vacuum
    If not indexed, returns {"exists": false, "status": "not_indexed"}.

    Args:
        path: Directory to check.
    """
    from ..commands.health import (
        _get_dedup_stats,
        _get_fts5_stats,
        _get_sqlite_info,
        _get_table_stats,
        _run_quick_check,
    )
    from ..commands.health import (
        _get_index_info as _health_index_info,
    )

    repo_root, db_path = _resolve_context(path)

    if not db_path.exists():
        return {"database": str(db_path), "exists": False, "status": "not_indexed"}

    con = connect(db_path, init_fts=False)
    try:
        current_branch = get_current_branch(repo_root)
        branch_counts = get_branch_file_counts(con)

        table_stats = _get_table_stats(con)
        indexes = _health_index_info(con)
        info = _get_sqlite_info(con, db_path)
        fts_stats = _get_fts5_stats(con)
        dedup_stats = _get_dedup_stats(con)
        quick_check = _run_quick_check(con)

        cur = con.cursor()
        cur.execute("SELECT model, dim FROM chunks LIMIT 1")
        model_row = cur.fetchone()

        total_size = db_path.stat().st_size
    finally:
        con.close()

    return {
        "database": str(db_path),
        "exists": True,
        "status": "healthy" if quick_check == "ok" else "issues_detected",
        "branch": current_branch,
        "branches": branch_counts,
        "tables": [
            {"name": name, "rows": rows, "size_bytes": size}
            for name, rows, size in table_stats
        ],
        "indexes": [
            {"name": name, "definition": defn}
            for name, defn in indexes
        ],
        "sqlite": info,
        "fts5": fts_stats,
        "dedup": dedup_stats,
        "quick_check": quick_check,
        "model": model_row[0] if model_row else None,
        "dimensions": model_row[1] if model_row else None,
        "total_size_bytes": total_size,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
