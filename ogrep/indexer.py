"""
Indexer module for ogrep.

Handles the core indexing logic: scanning directories, reading files,
chunking text, generating embeddings, and storing everything in the
database. Supports incremental updates by tracking file hashes.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
from collections.abc import Iterable, Sequence
from pathlib import Path

from tqdm import tqdm

from .chunking import chunk_lines as chunk_text
from .db import connect
from .embed import embed_texts
from .models import resolve_model

#: Directories to skip during indexing (version control, dependencies, caches)
DEFAULT_SKIP_DIRS = {".git", ".venv", "node_modules", ".ogrep", "__pycache__"}

#: Default exclude patterns for common non-source files
DEFAULT_EXCLUDES = (
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.exe",
    "*.egg-info/*",
    "*.egg",
    ".DS_Store",
    "Thumbs.db",
)


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


def _matches_pattern(path: Path, root: Path, patterns: Sequence[str]) -> bool:
    """
    Check if a path matches any of the exclude patterns.

    Patterns can be:
    - Simple globs: *.md, *.pyc
    - Directory globs: vendor/*, docs/*
    - Full path globs: **/test_*.py

    Args:
        path: File path to check.
        root: Root directory for relative path calculation.
        patterns: Sequence of glob patterns to match against.

    Returns:
        True if the path matches any pattern, False otherwise.
    """
    try:
        rel_path = path.relative_to(root)
    except ValueError:
        rel_path = path

    rel_str = str(rel_path)
    name = path.name

    for pattern in patterns:
        # Match against filename
        if fnmatch.fnmatch(name, pattern):
            return True
        # Match against relative path
        if fnmatch.fnmatch(rel_str, pattern):
            return True
        # Match with ** prefix for deep matching
        if "**" not in pattern and fnmatch.fnmatch(rel_str, f"**/{pattern}"):
            return True

    return False


def iter_files(
    root: Path,
    exclude: Sequence[str] = (),
    skip_dirs: set[str] | None = None,
) -> Iterable[Path]:
    """
    Recursively iterate over files in a directory, with filtering.

    Skips directories like .git, node_modules, .venv, etc. that typically
    contain non-source files. Supports exclude patterns for fine-grained
    file filtering.

    Args:
        root: Root directory to scan.
        exclude: Glob patterns for files to exclude (e.g., "*.md", "vendor/*").
        skip_dirs: Directory names to skip. Defaults to DEFAULT_SKIP_DIRS.

    Yields:
        Path objects for each file found.

    Example:
        >>> list(iter_files(Path("."), exclude=["*.md", "*.json"]))
    """
    if skip_dirs is None:
        skip_dirs = DEFAULT_SKIP_DIRS

    all_excludes = list(DEFAULT_EXCLUDES) + list(exclude)

    for dirpath, dirnames, filenames in os.walk(root):
        # Modify dirnames in-place to skip certain directories
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            p = Path(dirpath) / fn
            if all_excludes and _matches_pattern(p, root, all_excludes):
                continue
            yield p


def index_path(
    root: Path,
    db_path: Path,
    model: str | None = None,
    dimensions: int | None = None,
    chunk_lines: int = 120,
    overlap: int = 20,
    max_bytes: int = 2_000_000,
    exclude: Sequence[str] = (),
) -> None:
    """
    Index a directory for semantic search.

    Scans all files under root, chunks text files, generates embeddings,
    and stores them in the database. Supports incremental updates by
    checking file modification time, size, and content hash.

    Args:
        root: Directory to index.
        db_path: Path to the SQLite database file.
        model: OpenAI embedding model name or alias (None for default/env).
        dimensions: Embedding dimensions (None for model default).
        chunk_lines: Number of lines per chunk.
        overlap: Number of overlapping lines between chunks.
        max_bytes: Maximum file size to index (larger files are skipped).
        exclude: Glob patterns for files to exclude (e.g., "*.md", "vendor/*").

    Note:
        Files are skipped if:
        - They match an exclude pattern
        - They exceed max_bytes in size
        - They appear to be binary (contain null bytes)
        - They haven't changed since last indexing (same mtime, size, hash)

    Example:
        >>> index_path(
        ...     root=Path("."),
        ...     db_path=Path(".ogrep/index.sqlite"),
        ...     exclude=["*.md", "docs/*"],
        ... )
    """
    # Resolve model from arg, env, or default
    model = resolve_model(model)

    con = connect(db_path)

    files = list(iter_files(root, exclude=exclude))
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
