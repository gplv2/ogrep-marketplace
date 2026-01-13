"""
Database module for ogrep.

Provides SQLite database connection and schema management for storing
file metadata and embedding chunks. Uses WAL mode for better concurrent
read performance and foreign keys for referential integrity.

Schema:
    files: Tracks indexed files with path, modification time, size, and hash.
    chunks: Stores text chunks with embeddings, linked to files via foreign key.
    chunks_fts: FTS5 full-text index on chunk text for hybrid search.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

#: SQL schema for the ogrep database.
#: Uses WAL journal mode for performance and foreign keys for integrity.
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  mtime_ns INTEGER NOT NULL,
  size INTEGER NOT NULL,
  sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  text TEXT NOT NULL,
  text_sha256 TEXT NOT NULL,
  embedding BLOB NOT NULL,
  dim INTEGER NOT NULL,
  model TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(file_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_text_sha256 ON chunks(text_sha256);

-- History table for tracking index operations
-- Used by AI tools to understand what changed (refresh + log workflow)
CREATE TABLE IF NOT EXISTS index_history (
  id INTEGER PRIMARY KEY,
  timestamp TEXT NOT NULL DEFAULT (datetime('now')),
  action TEXT NOT NULL,  -- 'index', 'delete', 'clean', 'refresh', 'reindex'
  files_affected INTEGER NOT NULL DEFAULT 0,
  chunks_affected INTEGER NOT NULL DEFAULT 0,
  details TEXT,  -- JSON with action-specific details
  CONSTRAINT valid_action CHECK (action IN ('index', 'delete', 'clean', 'refresh', 'reindex'))
);

CREATE INDEX IF NOT EXISTS idx_history_timestamp ON index_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_history_action ON index_history(action);

-- Metadata table for index-wide settings
-- Stores key-value pairs like ast_mode, created_at, etc.
CREATE TABLE IF NOT EXISTS index_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

#: FTS5 schema for full-text search on chunk text.
#: Applied separately since FTS5 may not be available on all SQLite builds.
FTS5_SCHEMA = """
-- FTS5 virtual table for keyword search
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content='chunks',
    content_rowid='id'
);

-- Triggers to keep FTS index in sync with chunks table
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


def connect(db_path: Path, init_fts: bool = True) -> sqlite3.Connection:
    """
    Connect to the ogrep SQLite database, creating it if necessary.

    Creates the parent directory if it doesn't exist, opens the database,
    and initializes the schema if tables don't exist.

    Args:
        db_path: Path to the SQLite database file.
        init_fts: Whether to initialize FTS5 schema (default: True).
            Set to False to skip FTS5 initialization for faster connections
            when full-text search is not needed.

    Returns:
        An open sqlite3.Connection with the schema initialized.

    Example:
        >>> con = connect(Path(".ogrep/index.sqlite"))
        >>> con.execute("SELECT COUNT(*) FROM files").fetchone()
        (0,)
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.executescript(SCHEMA)

    if init_fts:
        try:
            con.executescript(FTS5_SCHEMA)
        except sqlite3.OperationalError:
            # FTS5 not available in this SQLite build - silently continue
            pass

    return con


def has_fts5(con: sqlite3.Connection) -> bool:
    """
    Check if FTS5 index is available in the database.

    Args:
        con: Open database connection.

    Returns:
        True if chunks_fts table exists and is functional.
    """
    try:
        # Check if the table exists
        result = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
        ).fetchone()
        return result is not None
    except sqlite3.OperationalError:
        return False


def log_history(
    con: sqlite3.Connection,
    action: str,
    files_affected: int = 0,
    chunks_affected: int = 0,
    details: dict | None = None,
) -> int:
    """
    Log an index operation to history.

    AI TOOL HINT: Use `ogrep log --json` to query this history.
    Combined with `ogrep index --refresh`, this lets you track what
    changed since your last check.

    Args:
        con: Open database connection.
        action: Operation type ('index', 'delete', 'clean', 'refresh', 'reindex').
        files_affected: Number of files affected.
        chunks_affected: Number of chunks affected.
        details: Optional dict with action-specific details (stored as JSON).

    Returns:
        The history entry ID.
    """
    import json as json_module

    details_json = json_module.dumps(details) if details else None
    cur = con.execute(
        """
        INSERT INTO index_history (action, files_affected, chunks_affected, details)
        VALUES (?, ?, ?, ?)
        """,
        (action, files_affected, chunks_affected, details_json),
    )
    con.commit()
    return cur.lastrowid


def rebuild_fts5(con: sqlite3.Connection) -> int:
    """
    Rebuild the FTS5 index from existing chunks.

    Use this to populate FTS5 after upgrading an existing database,
    or to repair a corrupted FTS5 index.

    Args:
        con: Open database connection.

    Returns:
        Number of chunks indexed.

    Raises:
        sqlite3.OperationalError: If FTS5 is not available.
    """
    # Drop and recreate FTS5 schema to ensure clean state
    # This handles cases where the table exists but is corrupted
    con.execute("DROP TABLE IF EXISTS chunks_fts")
    con.execute("DROP TRIGGER IF EXISTS chunks_fts_ai")
    con.execute("DROP TRIGGER IF EXISTS chunks_fts_ad")
    con.execute("DROP TRIGGER IF EXISTS chunks_fts_au")
    con.executescript(FTS5_SCHEMA)

    # Rebuild from chunks table
    con.execute("INSERT INTO chunks_fts(rowid, text) SELECT id, text FROM chunks")
    con.commit()

    # Return count
    return con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]


def get_metadata(con: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    """
    Get a metadata value from the index.

    Args:
        con: Open database connection.
        key: Metadata key to retrieve.
        default: Default value if key not found.

    Returns:
        The metadata value, or default if not found.
    """
    row = con.execute(
        "SELECT value FROM index_metadata WHERE key = ?", (key,)
    ).fetchone()
    return row[0] if row else default


def set_metadata(con: sqlite3.Connection, key: str, value: str) -> None:
    """
    Set a metadata value in the index.

    Uses INSERT OR REPLACE to upsert the value.

    Args:
        con: Open database connection.
        key: Metadata key to set.
        value: Value to store.
    """
    con.execute(
        """
        INSERT OR REPLACE INTO index_metadata (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        """,
        (key, value),
    )
    con.commit()


def get_all_metadata(con: sqlite3.Connection) -> dict[str, str]:
    """
    Get all metadata from the index.

    Returns:
        Dict of key-value pairs.
    """
    rows = con.execute("SELECT key, value FROM index_metadata").fetchall()
    return {k: v for k, v in rows}
