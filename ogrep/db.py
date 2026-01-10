"""
Database module for ogrep.

Provides SQLite database connection and schema management for storing
file metadata and embedding chunks. Uses WAL mode for better concurrent
read performance and foreign keys for referential integrity.

Schema:
    files: Tracks indexed files with path, modification time, size, and hash.
    chunks: Stores text chunks with embeddings, linked to files via foreign key.
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
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """
    Connect to the ogrep SQLite database, creating it if necessary.

    Creates the parent directory if it doesn't exist, opens the database,
    and initializes the schema if tables don't exist.

    Args:
        db_path: Path to the SQLite database file.

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
    return con
