"""
Health command for ogrep.

Displays comprehensive database diagnostics including table sizes,
indexes, SQLite info, FTS5 stats, and integrity checks. Supports
repair operations via flags.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from ._common import resolve_db_path


def _format_size(size_bytes: int) -> str:
    """Format byte size into human-readable string."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} bytes"


def _get_table_stats(con: sqlite3.Connection) -> list[tuple[str, int, int]]:
    """
    Get row count and estimated size for each table.

    Returns:
        List of (table_name, row_count, size_bytes) tuples.
    """
    stats = []
    cur = con.cursor()

    # Get all tables (including virtual tables for FTS5)
    cur.execute(
        "SELECT name, type FROM sqlite_master WHERE "
        "(type='table' OR type='table') AND name NOT LIKE 'sqlite_%'"
    )
    tables = [row[0] for row in cur.fetchall()]

    # Also check for FTS5 virtual tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts'")
    fts_tables = [row[0] for row in cur.fetchall()]

    for table in tables:
        # Row count
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            row_count = cur.fetchone()[0]
        except sqlite3.OperationalError:
            continue

        # Calculate size by sampling or using page info
        # Estimate based on table type
        if table == "chunks":
            # chunks table has BLOBs, estimate ~8KB per row average
            size_bytes = row_count * 8192
        elif table in fts_tables or "_fts" in table:
            # FTS5 tables are typically 10% of source
            size_bytes = row_count * 100
        elif table == "files":
            # files table is small, ~200 bytes per row
            size_bytes = row_count * 200
        else:
            size_bytes = row_count * 100

        stats.append((table, row_count, size_bytes))

    return sorted(stats, key=lambda x: x[0])


def _get_index_info(con: sqlite3.Connection) -> list[tuple[str, str]]:
    """
    Get all indexes and their definitions.

    Returns:
        List of (index_name, definition) tuples.
    """
    cur = con.cursor()
    cur.execute(
        """
        SELECT name, sql FROM sqlite_master
        WHERE type='index' AND sql IS NOT NULL
        ORDER BY name
        """
    )
    indexes = []
    for name, sql in cur.fetchall():
        # Extract ON clause from CREATE INDEX statement
        if sql and " ON " in sql:
            on_clause = sql.split(" ON ", 1)[1].rstrip(")")
            indexes.append((name, f"ON {on_clause})"))
        else:
            indexes.append((name, sql or ""))
    return indexes


def _get_sqlite_info(con: sqlite3.Connection, db_path: Path) -> dict:
    """Get SQLite database information."""
    cur = con.cursor()
    info = {}

    # SQLite version
    cur.execute("SELECT sqlite_version()")
    info["version"] = cur.fetchone()[0]

    # Journal mode
    cur.execute("PRAGMA journal_mode")
    info["journal"] = cur.fetchone()[0].upper()

    # Page size
    cur.execute("PRAGMA page_size")
    info["page_size"] = cur.fetchone()[0]

    # Page count
    cur.execute("PRAGMA page_count")
    info["page_count"] = cur.fetchone()[0]

    # Freelist count (reclaimable pages)
    cur.execute("PRAGMA freelist_count")
    info["freelist"] = cur.fetchone()[0]

    # Calculate reclaimable space
    info["reclaimable"] = info["freelist"] * info["page_size"]

    return info


def _get_dedup_stats(con: sqlite3.Connection) -> dict | None:
    """
    Get cross-file chunk deduplication statistics.

    Returns:
        Dictionary with total_chunks, unique_hashes, duplicated, dedup_ratio.
        None if no chunks exist.
    """
    cur = con.cursor()

    # Total chunks
    cur.execute("SELECT COUNT(*) FROM chunks")
    total_chunks = cur.fetchone()[0]

    if total_chunks == 0:
        return None

    # Unique text_sha256 hashes
    cur.execute("SELECT COUNT(DISTINCT text_sha256) FROM chunks")
    unique_hashes = cur.fetchone()[0]

    # Duplicates = chunks that share a hash with another chunk
    duplicated = total_chunks - unique_hashes

    # Ratio: percentage of embedding storage saved
    dedup_ratio = (duplicated / total_chunks * 100) if total_chunks > 0 else 0.0

    return {
        "total_chunks": total_chunks,
        "unique_hashes": unique_hashes,
        "duplicated": duplicated,
        "dedup_ratio": dedup_ratio,
    }


def _get_fts5_stats(con: sqlite3.Connection) -> dict | None:
    """Get FTS5 index statistics if available."""
    cur = con.cursor()

    # Check if FTS5 table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'")
    if not cur.fetchone():
        return None

    try:
        # Get token count from FTS5
        cur.execute("SELECT COUNT(*) FROM chunks_fts")
        row_count = cur.fetchone()[0]

        # Get vocabulary stats using fts5vocab if possible
        # This requires creating a virtual table, so we'll estimate instead
        cur.execute("SELECT SUM(LENGTH(text)) FROM chunks")
        total_text_size = cur.fetchone()[0] or 0

        # Rough estimate: average word is 6 chars, so tokens ≈ size / 7
        estimated_tokens = total_text_size // 7

        # Unique terms estimate: typically 10-20% of total tokens for code
        estimated_unique = estimated_tokens // 5

        return {
            "rows": row_count,
            "tokens_estimate": estimated_tokens,
            "unique_estimate": estimated_unique,
        }
    except sqlite3.OperationalError:
        return None


def _run_quick_check(con: sqlite3.Connection) -> str:
    """Run PRAGMA quick_check and return result."""
    cur = con.cursor()
    cur.execute("PRAGMA quick_check")
    result = cur.fetchone()[0]
    return result


def _run_integrity_check(con: sqlite3.Connection) -> list[str]:
    """Run full PRAGMA integrity_check and return results."""
    cur = con.cursor()
    cur.execute("PRAGMA integrity_check")
    results = [row[0] for row in cur.fetchall()]
    return results


def _do_vacuum(con: sqlite3.Connection, db_path: Path) -> tuple[int, int]:
    """
    Run VACUUM and return (before_size, after_size).
    """
    before_size = db_path.stat().st_size
    con.execute("VACUUM")
    con.commit()
    after_size = db_path.stat().st_size
    return before_size, after_size


def _do_rebuild_fts(con: sqlite3.Connection) -> int:
    """
    Rebuild FTS5 index from chunks table.

    Returns:
        Number of chunks indexed.
    """
    cur = con.cursor()

    # Drop existing FTS5 objects
    cur.execute("DROP TABLE IF EXISTS chunks_fts")
    cur.execute("DROP TRIGGER IF EXISTS chunks_fts_ai")
    cur.execute("DROP TRIGGER IF EXISTS chunks_fts_ad")
    cur.execute("DROP TRIGGER IF EXISTS chunks_fts_au")

    # Recreate FTS5 schema
    cur.executescript(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            text,
            content='chunks',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS chunks_fts_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_fts_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_fts_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
            INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
        END;
        """
    )

    # Populate from chunks
    cur.execute("INSERT INTO chunks_fts(rowid, text) SELECT id, text FROM chunks")
    con.commit()

    # Return count
    cur.execute("SELECT COUNT(*) FROM chunks_fts")
    return cur.fetchone()[0]


def cmd_health(args: argparse.Namespace) -> int:
    """
    Show database health and diagnostics, optionally repair.

    Displays comprehensive information about the ogrep database including:
        - Table row counts and sizes
        - Index definitions
        - SQLite configuration (version, journal mode, page info)
        - FTS5 statistics
        - Quick integrity check

    Repair flags:
        --vacuum: Reclaim space and defragment database
        --rebuild-fts: Drop and rebuild FTS5 index
        --reindex: Full reindex of all files (re-embeds everything)
        --integrity: Run full integrity check (slow)
        --full: vacuum + rebuild-fts + integrity (not reindex)

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for issues).
    """
    repo_root = args.repo_root.resolve() if args.repo_root else Path.cwd()
    db_path = resolve_db_path(args.db, args.profile, args.global_cache, repo_root)
    use_json = getattr(args, "json", False)

    if not use_json:
        print(f"Database: {db_path}")

    if not db_path.exists():
        if use_json:
            print(json.dumps({"database": str(db_path), "exists": False, "status": "not_indexed"}))
        else:
            print("Status: Not indexed")
        return 0

    con = sqlite3.connect(str(db_path))
    exit_code = 0

    try:
        # Handle repair flags first
        if args.full:
            args.vacuum = True
            args.rebuild_fts = True
            args.integrity = True

        if args.vacuum:
            print("\n── Vacuum ──")
            before, after = _do_vacuum(con, db_path)
            saved = before - after
            print(f"  Before: {_format_size(before)}")
            print(f"  After:  {_format_size(after)}")
            if saved > 0:
                print(f"  Reclaimed: {_format_size(saved)}")
            else:
                print("  No space reclaimed")

        if args.rebuild_fts:
            print("\n── Rebuild FTS5 ──")
            try:
                count = _do_rebuild_fts(con)
                print(f"  Indexed {count} chunks")
            except sqlite3.OperationalError as e:
                print(f"  Error: {e}")
                exit_code = 1

        if args.reindex:
            print("\n── Reindex ──")
            print("  Use 'ogrep reindex .' to rebuild the full index")
            print("  (Not run automatically - requires re-embedding)")

        # Run integrity check
        if args.integrity:
            print("\n── Full Integrity Check ──")
            results = _run_integrity_check(con)
            if results == ["ok"]:
                print("  Result: OK")
            else:
                print("  Issues found:")
                for r in results[:10]:
                    print(f"    {r}")
                if len(results) > 10:
                    print(f"    ... and {len(results) - 10} more")
                exit_code = 1
        else:
            # If we did any repair, don't show full diagnostic
            if not (args.vacuum or args.rebuild_fts):
                pass  # Show full diagnostic below

        # Show full diagnostic if no repair flags (or after repairs)
        if not (args.vacuum or args.rebuild_fts or args.integrity or args.reindex):
            # Collect all diagnostic data
            table_stats = _get_table_stats(con)
            indexes = _get_index_info(con)
            info = _get_sqlite_info(con, db_path)
            fts_stats = _get_fts5_stats(con)
            dedup_stats = _get_dedup_stats(con)
            quick_check = _run_quick_check(con)
            total_size = db_path.stat().st_size

            # Get embedding model
            cur = con.cursor()
            cur.execute("SELECT model, dim FROM chunks LIMIT 1")
            model_row = cur.fetchone()

            if quick_check != "ok":
                exit_code = 1

            if use_json:
                output = {
                    "database": str(db_path),
                    "exists": True,
                    "tables": [
                        {"name": name, "rows": rows, "size_bytes": size}
                        for name, rows, size in table_stats
                    ],
                    "indexes": [
                        {"name": name, "definition": definition}
                        for name, definition in indexes
                    ],
                    "sqlite": info,
                    "fts5": fts_stats,
                    "dedup": dedup_stats,
                    "quick_check": quick_check,
                    "model": model_row[0] if model_row else None,
                    "dimensions": model_row[1] if model_row else None,
                    "total_size_bytes": total_size,
                    "status": "healthy" if exit_code == 0 else "issues_detected",
                }
                print(json.dumps(output))
            else:
                # Tables
                print("\n── Tables ──")
                for name, rows, size in table_stats:
                    fts_marker = "  (FTS5)" if name == "chunks_fts" else ""
                    print(f"  {name:<12} {rows:>6} rows  {_format_size(size):>10}{fts_marker}")

                # Indexes
                print("\n── Indexes ──")
                if indexes:
                    for name, definition in indexes:
                        print(f"  {name:<25} {definition}")
                else:
                    print("  No user indexes")

                # SQLite info
                print("\n── SQLite Info ──")
                print(f"  Version: {info['version']}")
                print(f"  Journal: {info['journal']}")
                print(f"  Page size: {info['page_size']}")
                print(f"  Page count: {info['page_count']}")
                if info["freelist"] > 0:
                    print(
                        f"  Freelist: {info['freelist']} pages "
                        f"({_format_size(info['reclaimable'])} reclaimable)"
                    )
                else:
                    print("  Freelist: 0 pages")

                # FTS5 stats
                if fts_stats:
                    print("\n── FTS5 Stats ──")
                    print(f"  Rows indexed: {fts_stats['rows']:,}")
                    print(f"  Tokens (est): {fts_stats['tokens_estimate']:,}")
                    print(f"  Unique terms (est): {fts_stats['unique_estimate']:,}")
                else:
                    print("\n── FTS5 Stats ──")
                    print("  Not available (run 'ogrep reindex .' to enable)")

                # Dedup stats
                if dedup_stats:
                    print("\n── Dedup Stats ──")
                    print(f"  Total chunks: {dedup_stats['total_chunks']:,}")
                    print(f"  Unique hashes: {dedup_stats['unique_hashes']:,}")
                    if dedup_stats["duplicated"] > 0:
                        print(
                            f"  Deduplicated: {dedup_stats['duplicated']:,} "
                            f"({dedup_stats['dedup_ratio']:.1f}% embedding savings)"
                        )
                    else:
                        print("  Deduplicated: 0 (0% - no duplicates found)")

                # Quick check
                print("\n── Quick Check ──")
                if quick_check == "ok":
                    print("  Result: OK")
                else:
                    print(f"  Result: {quick_check}")

                # Embedding model
                if model_row:
                    print("\n── Embedding Model ──")
                    print(f"  Model: {model_row[0]}")
                    print(f"  Dimensions: {model_row[1]}")

                # Total size
                print(f"\nTotal size: {_format_size(total_size)}")

                # Status summary
                if exit_code == 0:
                    print("\nStatus: Healthy")
                else:
                    print("\nStatus: Issues detected")

    except KeyboardInterrupt:
        con.close()
        if use_json:
            print(json.dumps({"error": "Interrupted by user (Ctrl-C)"}))
        else:
            print("\n\nInterrupted by user (Ctrl-C).")
            print("Health check cancelled.")
        return 130  # Standard SIGINT exit code (128 + 2)

    con.close()
    return exit_code
