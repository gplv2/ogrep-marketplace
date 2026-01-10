"""
Indexer module for ogrep.

Handles the core indexing logic: scanning directories, reading files,
chunking text, generating embeddings, and storing everything in the
database. Supports incremental updates by tracking file hashes.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from pathlib import Path

from tqdm import tqdm

from .chunking import chunk_lines as chunk_text
from .db import connect
from .embed import embed_texts

#: Directories to skip during indexing (version control, dependencies, caches)
DEFAULT_SKIP_DIRS = {".git", ".venv", "node_modules", ".ogrep", "__pycache__"}


def _sha256_bytes(b: bytes) -> str:
    """
    Compute SHA-256 hash of bytes.

    Args:
        b: Input bytes.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    return hashlib.sha256(b).hexdigest()


def _is_probably_text(b: bytes) -> bool:
    """
    Heuristic check for text files (no null bytes).

    Binary files typically contain null bytes, while text files don't.
    This is a fast heuristic that works well in practice.

    Args:
        b: File contents as bytes.

    Returns:
        True if the content appears to be text, False otherwise.
    """
    return b.find(b"\x00") == -1


def iter_files(root: Path) -> Iterable[Path]:
    """
    Recursively iterate over files in a directory, skipping common non-source dirs.

    Skips directories like .git, node_modules, .venv, etc. that typically
    contain non-source files.

    Args:
        root: Root directory to scan.

    Yields:
        Path objects for each file found.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        # Modify dirnames in-place to skip certain directories
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_SKIP_DIRS]
        for fn in filenames:
            yield Path(dirpath) / fn


def index_path(
    root: Path,
    db_path: Path,
    model: str = "text-embedding-3-small",
    dimensions: int | None = None,
    chunk_lines: int = 120,
    overlap: int = 20,
    max_bytes: int = 2_000_000,
) -> None:
    """
    Index a directory for semantic search.

    Scans all files under root, chunks text files, generates embeddings,
    and stores them in the database. Supports incremental updates by
    checking file modification time, size, and content hash.

    Args:
        root: Directory to index.
        db_path: Path to the SQLite database file.
        model: OpenAI embedding model name.
        dimensions: Embedding dimensions (None for model default).
        chunk_lines: Number of lines per chunk.
        overlap: Number of overlapping lines between chunks.
        max_bytes: Maximum file size to index (larger files are skipped).

    Note:
        Files are skipped if:
        - They exceed max_bytes in size
        - They appear to be binary (contain null bytes)
        - They haven't changed since last indexing (same mtime, size, hash)

    Example:
        >>> index_path(
        ...     root=Path("."),
        ...     db_path=Path(".ogrep/index.sqlite"),
        ...     model="text-embedding-3-small",
        ... )
    """
    con = connect(db_path)

    files = list(iter_files(root))
    for p in tqdm(files, desc="Indexing"):
        if not p.is_file():
            continue

        # Get file stats
        try:
            st = p.stat()
        except FileNotFoundError:
            continue

        # Skip large files
        if st.st_size > max_bytes:
            continue

        # Read file contents
        try:
            b = p.read_bytes()
        except Exception:
            continue

        # Skip binary files
        if not _is_probably_text(b):
            continue

        sha = _sha256_bytes(b)
        rel = str(p.resolve())

        # Check if file is already indexed and unchanged
        row = con.execute(
            "SELECT id, mtime_ns, size, sha256 FROM files WHERE path=?",
            (rel,),
        ).fetchone()

        if (
            row
            and int(row[1]) == st.st_mtime_ns
            and int(row[2]) == st.st_size
            and str(row[3]) == sha
        ):
            continue  # File unchanged, skip

        # Update or insert file record
        if row:
            file_id = int(row[0])
            con.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
            con.execute(
                "UPDATE files SET mtime_ns=?, size=?, sha256=? WHERE id=?",
                (st.st_mtime_ns, st.st_size, sha, file_id),
            )
        else:
            cur = con.execute(
                "INSERT INTO files(path, mtime_ns, size, sha256) VALUES(?,?,?,?)",
                (rel, st.st_mtime_ns, st.st_size, sha),
            )
            file_id = int(cur.lastrowid)

        # Chunk the file content
        text = b.decode("utf-8", errors="ignore")
        chunks = chunk_text(text, chunk_size=chunk_lines, overlap=overlap)
        if not chunks:
            continue

        # Generate embeddings
        texts = [c.text.replace("\r\n", "\n") for c in chunks]
        emb_blobs, dim = embed_texts(texts, model=model, dimensions=dimensions)

        # Store chunks with embeddings
        for c, emb in zip(chunks, emb_blobs, strict=True):
            tsha = hashlib.sha256(c.text.encode("utf-8", errors="ignore")).hexdigest()
            con.execute(
                """INSERT INTO chunks(file_id, chunk_index, start_line, end_line,
                   text, text_sha256, embedding, dim, model)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (file_id, c.chunk_index, c.start_line, c.end_line, c.text, tsha, emb, dim, model),
            )

        con.commit()
