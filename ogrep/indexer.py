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
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from .chunking import chunk_lines as chunk_text
from .db import connect
from .embed import embed_texts
from .filetype import detect_file_types_batch, has_file_command
from .models import get_model, resolve_model

#: Directories to skip during indexing (version control, dependencies, caches)
DEFAULT_SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",  # Mercurial
    ".venv",
    "venv",
    "node_modules",
    ".ogrep",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    ".githooks",
    "storage",  # Laravel/framework cache directories
}

#: Default exclude patterns for common non-source files
DEFAULT_EXCLUDES = (
    # Binary/compiled
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.exe",
    "*.egg-info/*",
    "*.egg",
    "*.whl",
    "*.dist-info/*",
    # OS files
    ".DS_Store",
    "Thumbs.db",
    # Git metadata
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    ".gitkeep",
    # Environment/secrets (never index these!)
    ".env",
    ".env.*",
    "*.env",
    ".envrc",
    "secrets.*",
    "credentials.*",
    # Documentation (index source code, not docs)
    "*.md",
    "*.txt",
    "*.rst",
    "docs/*",
    # Config/data files
    "*.json",
    "*.yaml",
    "*.yml",
    "*.toml",
    "*.ini",
    "*.cfg",
    "*.conf",
    ".editorconfig",
    # Lock files
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Cargo.lock",
    "Gemfile.lock",
    # Build outputs
    "dist/*",
    "build/*",
    "out/*",
    "target/*",
    # Minified files
    "*.min.js",
    "*.min.css",
    "*.map",
    # Test/coverage
    "coverage/*",
    ".coverage",
    "htmlcov/*",
    ".phpunit.result.cache",
    # Vendor directories
    "vendor/*",
    "third_party/*",
    # Common non-source
    "LICENSE*",
    "LICENCE*",
    "COPYING*",
    "Makefile",
    "Dockerfile",
    "*.dockerfile",
    # Logs and temp files
    "*.log",
    "logs/*",
    "*.tmp",
    "*.temp",
    # Backup files
    "*.old",
    "*.bak",
    "*.backup",
    "*.orig",
    "*.swp",
    "*~",
    # Data files
    "*.csv",
    "*.tsv",
    "*.sqlt",
    "*.dat",
    "*.xml",
    # Images (also filtered by binary detection, but skip early)
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.bmp",
    "*.ico",
    "*.svg",
    "*.webp",
    "*.tiff",
    "*.tif",
    "*.psd",
    "*.ai",
    "*.eps",
    # Fonts
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.otf",
    "*.eot",
    # Audio/video
    "*.mp3",
    "*.mp4",
    "*.wav",
    "*.avi",
    "*.mov",
    "*.webm",
    # Archives
    "*.zip",
    "*.tar",
    "*.gz",
    "*.rar",
    "*.7z",
    # Database files
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    "*.sql",
    "*.dump",
    # Python package metadata
    "*.pth",
    "py.typed",
)


def load_ogrepignore(root: Path) -> list[str]:
    """
    Load exclude patterns from .ogrepignore file.

    The file format is similar to .gitignore:
    - One pattern per line
    - Lines starting with # are comments
    - Empty lines are ignored
    - Patterns use glob syntax (*.sql, vendor/*, etc.)

    Args:
        root: Directory to look for .ogrepignore file.

    Returns:
        List of exclude patterns (empty if file doesn't exist).

    Example .ogrepignore file:
        # Exclude SQL files
        *.sql

        # Exclude generated code
        generated/*
    """
    ignore_file = root / ".ogrepignore"
    if not ignore_file.is_file():
        return []

    patterns = []
    try:
        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
    except Exception:
        return []

    return patterns


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
    include: Sequence[str] = (),
    skip_dirs: set[str] | None = None,
) -> Iterable[Path]:
    """
    Recursively iterate over files in a directory, with filtering.

    Skips directories like .git, node_modules, .venv, etc. that typically
    contain non-source files. Supports exclude/include patterns for
    fine-grained file filtering.

    Also skips:
    - Empty files (0 bytes)
    - Duplicate symlinks (symlinks pointing to already-seen files)

    Args:
        root: Root directory to scan.
        exclude: Additional glob patterns to exclude (added to defaults).
        include: Glob patterns to include even if they match excludes.
            Use to override defaults, e.g., include=["*.md"] to index markdown.
        skip_dirs: Directory names to skip. Defaults to DEFAULT_SKIP_DIRS.

    Yields:
        Path objects for each file found.

    Example:
        >>> list(iter_files(Path("."), exclude=["test_*"]))
        >>> list(iter_files(Path("."), include=["*.md"]))  # Override default exclude
    """
    if skip_dirs is None:
        skip_dirs = DEFAULT_SKIP_DIRS

    all_excludes = list(DEFAULT_EXCLUDES) + list(exclude)

    # Track real paths to avoid duplicate symlinks
    seen_real_paths: set[Path] = set()

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Modify dirnames in-place to skip certain directories
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            p = Path(dirpath) / fn

            # Skip symlinks to already-seen files (dedup)
            try:
                real_path = p.resolve()
                if real_path in seen_real_paths:
                    continue
                seen_real_paths.add(real_path)

                # Skip empty files (0 bytes)
                if p.stat().st_size == 0:
                    continue
            except (OSError, FileNotFoundError):
                # Broken symlink or permission error
                continue

            # Check if explicitly included (overrides excludes)
            if include and _matches_pattern(p, root, include):
                yield p
                continue
            # Check excludes
            if all_excludes and _matches_pattern(p, root, all_excludes):
                continue
            yield p


@dataclass
class IndexStats:
    """Statistics from an indexing operation."""

    files_scanned: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    chunks_total: int = 0
    chunks_reused: int = 0
    chunks_reused_global: int = 0  # Reused from other files
    chunks_reused_local: int = 0  # Reused from same file edit
    chunks_embedded: int = 0

    @property
    def tokens_saved_estimate(self) -> int:
        """Estimate tokens saved by reusing embeddings (~100 tokens per chunk)."""
        return self.chunks_reused * 100

    @property
    def dedup_ratio(self) -> float:
        """Percentage of chunks that were deduplicated."""
        if self.chunks_total == 0:
            return 0.0
        return self.chunks_reused / self.chunks_total * 100


def _find_global_embeddings(
    con,
    chunk_hashes: list[str],
    model: str,
    expected_dim: int,
) -> dict[str, tuple[bytes, int]]:
    """
    Find existing embeddings across ALL files for given chunk hashes.

    Performs integrity checks:
    - Model must match
    - Embedding dimension must match expected

    Args:
        con: Database connection.
        chunk_hashes: List of text_sha256 hashes to look up.
        model: Required embedding model name.
        expected_dim: Expected embedding dimensions for this model.

    Returns:
        Dict mapping text_sha256 -> (embedding_bytes, dim).
    """
    if not chunk_hashes:
        return {}

    # Batch query with model filter
    placeholders = ",".join("?" * len(chunk_hashes))
    rows = con.execute(
        f"""SELECT DISTINCT text_sha256, embedding, dim
            FROM chunks
            WHERE text_sha256 IN ({placeholders})
              AND model = ?
        """,
        (*chunk_hashes, model),
    ).fetchall()

    result = {}
    for text_sha256, embedding, dim in rows:
        # Integrity check: Verify dimensions match model
        if dim != expected_dim:
            continue  # Skip mismatched dimensions

        result[text_sha256] = (embedding, dim)

    return result


def index_path(
    root: Path,
    db_path: Path,
    model: str | None = None,
    dimensions: int | None = None,
    chunk_lines: int = 60,
    overlap: int = 10,
    max_bytes: int = 2_000_000,
    exclude: Sequence[str] = (),
    include: Sequence[str] = (),
    detect: bool = True,
) -> IndexStats:
    """
    Index a directory for semantic search.

    Scans all files under root, chunks text files, generates embeddings,
    and stores them in the database. Supports incremental updates by
    checking file modification time, size, and content hash.

    Smart embedding reuse: When a file changes, existing chunk embeddings
    are reused if the chunk text hasn't changed (matched by text_sha256).
    This saves API tokens for common edit patterns like appending code.

    By default, excludes common non-source files (docs, config, build outputs).
    Use --include to override specific excludes. Additional patterns can be
    specified in a .ogrepignore file in the root directory.

    Args:
        root: Directory to index.
        db_path: Path to the SQLite database file.
        model: OpenAI embedding model name or alias (None for default/env).
        dimensions: Embedding dimensions (None for model default).
        chunk_lines: Number of lines per chunk.
        overlap: Number of overlapping lines between chunks.
        max_bytes: Maximum file size to index (larger files are skipped).
        exclude: Additional glob patterns to exclude.
        include: Glob patterns to include (overrides default excludes).
        detect: Use file command for MIME type detection (default True).

    Returns:
        IndexStats with counts of files/chunks processed and reused.

    Note:
        Files are skipped if:
        - They match an exclude pattern (unless overridden by include)
        - They exceed max_bytes in size
        - They appear to be binary (contain null bytes)
        - They fail MIME type detection (if detect=True)
        - They haven't changed since last indexing (same mtime, size, hash)

    Example:
        >>> stats = index_path(
        ...     root=Path("."),
        ...     db_path=Path(".ogrep/index.sqlite"),
        ... )
        >>> print(f"Reused {stats.chunks_reused} chunks")
    """
    # Resolve model from arg, env, or default
    model = resolve_model(model)
    stats = IndexStats()

    # Load .ogrepignore patterns and combine with CLI excludes
    ignore_patterns = load_ogrepignore(root)
    all_exclude = list(exclude) + ignore_patterns

    con = connect(db_path)

    # Model consistency check - prevent mixing models in the same index
    existing_model_row = con.execute(
        "SELECT DISTINCT model FROM chunks LIMIT 1"
    ).fetchone()
    if existing_model_row and existing_model_row[0] != model:
        raise ValueError(
            f"Model mismatch: index uses '{existing_model_row[0]}' "
            f"but requested '{model}'. "
            f"Use --force to reindex with new model."
        )

    # Get expected dimensions - prefer actual DB dimension over model definition
    # This handles mocks and custom dimension overrides correctly
    # Use the MOST COMMON dimension to handle corrupted entries gracefully
    # In case of ties, prefer smaller dimension (more likely to be a standard model dimension)
    expected_dim = dimensions
    if expected_dim is None:
        # Check what dimension the majority of existing chunks use
        existing_dim_row = con.execute(
            """SELECT dim, COUNT(*) as cnt FROM chunks
               WHERE model = ?
               GROUP BY dim
               ORDER BY cnt DESC, dim ASC
               LIMIT 1""",
            (model,),
        ).fetchone()
        if existing_dim_row:
            expected_dim = existing_dim_row[0]
        else:
            # Fall back to model definition
            try:
                model_info = get_model(model)
                expected_dim = model_info.dimensions
            except KeyError:
                # Unknown model - will learn from first embed
                expected_dim = None

    files = list(iter_files(root, exclude=all_exclude, include=include))
    stats.files_scanned = len(files)

    # Batch file type detection (if enabled and file command available)
    detection_results = {}
    if detect and has_file_command() and files:
        detection_results = detect_file_types_batch(files)

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
            stats.files_skipped += 1
            continue

        # Read file contents
        try:
            b = p.read_bytes()
        except Exception:
            stats.files_skipped += 1
            continue

        # Skip binary files (null-byte check)
        if not _is_probably_text(b):
            stats.files_skipped += 1
            continue

        # Skip files that failed MIME type detection
        if p in detection_results and not detection_results[p].is_text:
            stats.files_skipped += 1
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
            stats.files_skipped += 1
            continue  # File unchanged, skip

        stats.files_indexed += 1

        # Cache existing embeddings before deletion (for reuse)
        existing_embeddings: dict[str, tuple[bytes, int]] = {}
        if row:
            file_id = int(row[0])
            for r in con.execute(
                "SELECT text_sha256, embedding, dim FROM chunks WHERE file_id=?",
                (file_id,),
            ):
                existing_embeddings[str(r[0])] = (r[1], int(r[2]))
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

        stats.chunks_total += len(chunks)

        # Compute text hashes for all chunks first
        chunk_hashes = []
        normalized_texts = []
        for c in chunks:
            normalized_text = c.text.replace("\r\n", "\n")
            tsha = hashlib.sha256(normalized_text.encode("utf-8", errors="ignore")).hexdigest()
            chunk_hashes.append(tsha)
            normalized_texts.append(normalized_text)

        # Query global embeddings for all hashes (cross-file deduplication)
        global_embeddings: dict[str, tuple[bytes, int]] = {}
        if expected_dim is not None:
            global_embeddings = _find_global_embeddings(
                con, chunk_hashes, model, expected_dim
            )

        # Identify reusable vs new chunks (global first, then local)
        chunks_to_embed = []
        reusable_indices = []  # (chunk_index, cached_embedding, cached_dim)

        for i, tsha in enumerate(chunk_hashes):
            if tsha in global_embeddings:
                # Found in another file - reuse with verified integrity
                reusable_indices.append((i, *global_embeddings[tsha]))
                stats.chunks_reused += 1
                stats.chunks_reused_global += 1
            elif tsha in existing_embeddings:
                # Found in this file's previous version
                reusable_indices.append(
                    (i, existing_embeddings[tsha][0], existing_embeddings[tsha][1])
                )
                stats.chunks_reused += 1
                stats.chunks_reused_local += 1
            else:
                # Truly new chunk - needs embedding
                chunks_to_embed.append((i, normalized_texts[i]))
                stats.chunks_embedded += 1

        # Generate embeddings only for new chunks
        new_embeddings: dict[int, tuple[bytes, int]] = {}
        if chunks_to_embed:
            texts = [t for _, t in chunks_to_embed]
            emb_blobs, dim = embed_texts(texts, model=model, dimensions=dimensions)
            for (idx, _), emb in zip(chunks_to_embed, emb_blobs, strict=True):
                new_embeddings[idx] = (emb, dim)
            # Learn dimension from embed if we didn't know it
            if expected_dim is None:
                expected_dim = dim

        # Store all chunks with embeddings (reused or new)
        for i, c in enumerate(chunks):
            tsha = chunk_hashes[i]
            if i in new_embeddings:
                emb, dim = new_embeddings[i]
            else:
                # Find in reusable
                emb, dim = next((e, d) for idx, e, d in reusable_indices if idx == i)

            con.execute(
                """INSERT INTO chunks(file_id, chunk_index, start_line, end_line,
                   text, text_sha256, embedding, dim, model)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (file_id, c.chunk_index, c.start_line, c.end_line, c.text, tsha, emb, dim, model),
            )

        con.commit()

    return stats
