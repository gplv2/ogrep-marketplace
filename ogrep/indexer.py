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
from .db import connect, log_history

# AST chunking - optional, lazy import
def _get_ast_chunker():
    """Lazy import AST chunker to avoid import errors if not installed."""
    try:
        from .ast_chunking import chunk_ast, is_ast_available
        if is_ast_available():
            return chunk_ast
    except ImportError:
        pass
    return None
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
    indexed_files: list[str] | None = None  # Paths of files that were indexed (verbose mode)

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


def _check_model_consistency(con, model: str) -> None:
    """
    Verify the requested model matches the index's existing model.

    Args:
        con: Database connection.
        model: Requested embedding model name.

    Raises:
        ValueError: If index uses a different model.
    """
    existing_model_row = con.execute("SELECT DISTINCT model FROM chunks LIMIT 1").fetchone()
    if existing_model_row and existing_model_row[0] != model:
        raise ValueError(
            f"Model mismatch: index uses '{existing_model_row[0]}' "
            f"but requested '{model}'. "
            f"Use --force to reindex with new model."
        )


def _get_expected_dimension(con, model: str, dimensions: int | None) -> int | None:
    """
    Determine expected embedding dimension for the model.

    Priority:
    1. Explicit dimensions argument
    2. Most common dimension in existing chunks for this model
    3. Model definition default
    4. None (learn from first embed)

    Args:
        con: Database connection.
        model: Embedding model name.
        dimensions: Explicit dimensions override (or None).

    Returns:
        Expected dimension, or None if unknown.
    """
    if dimensions is not None:
        return dimensions

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
        return existing_dim_row[0]

    # Fall back to model definition
    try:
        model_info = get_model(model)
        return model_info.dimensions
    except KeyError:
        # Unknown model - will learn from first embed
        return None


def _read_file_if_indexable(
    path: Path,
    max_bytes: int,
    detection_results: dict,
    stats: IndexStats,
) -> bytes | None:
    """
    Read file contents if the file is indexable.

    Checks:
    - File exists
    - Not too large
    - Not binary (no null bytes)
    - Passes MIME detection (if enabled)

    Args:
        path: File to read.
        max_bytes: Maximum file size.
        detection_results: MIME detection results (may be empty).
        stats: IndexStats to update on skip.

    Returns:
        File contents as bytes, or None if file should be skipped.
    """
    if not path.is_file():
        return None

    try:
        st = path.stat()
    except FileNotFoundError:
        return None

    # Skip large files
    if st.st_size > max_bytes:
        stats.files_skipped += 1
        return None

    # Read file contents
    try:
        b = path.read_bytes()
    except Exception:
        stats.files_skipped += 1
        return None

    # Skip binary files (null-byte check)
    if not _is_probably_text(b):
        stats.files_skipped += 1
        return None

    # Skip files that failed MIME type detection
    if path in detection_results and not detection_results[path].is_text:
        stats.files_skipped += 1
        return None

    return b


def _is_file_unchanged(con, rel_path: str, sha: str, mtime_ns: int, size: int) -> tuple:
    """
    Check if file is already indexed and unchanged.

    Args:
        con: Database connection.
        rel_path: Resolved file path.
        sha: SHA-256 hash of file contents.
        mtime_ns: Modification time in nanoseconds.
        size: File size in bytes.

    Returns:
        Tuple of (is_unchanged, existing_row).
        existing_row is None if file not in database.
    """
    row = con.execute(
        "SELECT id, mtime_ns, size, sha256 FROM files WHERE path=?",
        (rel_path,),
    ).fetchone()

    if row and int(row[1]) == mtime_ns and int(row[2]) == size and str(row[3]) == sha:
        return True, row

    return False, row


def _cache_existing_embeddings(con, file_id: int) -> dict[str, tuple[bytes, int]]:
    """
    Cache embeddings from existing file chunks before deletion.

    Args:
        con: Database connection.
        file_id: File ID to cache embeddings for.

    Returns:
        Dict mapping text_sha256 -> (embedding_bytes, dim).
    """
    embeddings = {}
    for r in con.execute(
        "SELECT text_sha256, embedding, dim FROM chunks WHERE file_id=?",
        (file_id,),
    ):
        embeddings[str(r[0])] = (r[1], int(r[2]))
    return embeddings


def _upsert_file_record(
    con,
    rel_path: str,
    mtime_ns: int,
    size: int,
    sha: str,
    existing_row: tuple | None,
) -> int:
    """
    Insert or update file record in database.

    Args:
        con: Database connection.
        rel_path: Resolved file path.
        mtime_ns: Modification time in nanoseconds.
        size: File size in bytes.
        sha: SHA-256 hash of file contents.
        existing_row: Existing row from files table (or None).

    Returns:
        File ID.
    """
    if existing_row:
        file_id = int(existing_row[0])
        con.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
        con.execute(
            "UPDATE files SET mtime_ns=?, size=?, sha256=? WHERE id=?",
            (mtime_ns, size, sha, file_id),
        )
    else:
        cur = con.execute(
            "INSERT INTO files(path, mtime_ns, size, sha256) VALUES(?,?,?,?)",
            (rel_path, mtime_ns, size, sha),
        )
        file_id = int(cur.lastrowid)
    return file_id


def _compute_chunk_hashes(chunks) -> tuple[list[str], list[str]]:
    """
    Compute SHA-256 hashes for all chunks.

    Args:
        chunks: List of Chunk objects.

    Returns:
        Tuple of (chunk_hashes, normalized_texts).
    """
    chunk_hashes = []
    normalized_texts = []
    for c in chunks:
        normalized_text = c.text.replace("\r\n", "\n")
        tsha = hashlib.sha256(normalized_text.encode("utf-8", errors="ignore")).hexdigest()
        chunk_hashes.append(tsha)
        normalized_texts.append(normalized_text)
    return chunk_hashes, normalized_texts


def _classify_chunks_for_embedding(
    chunk_hashes: list[str],
    normalized_texts: list[str],
    global_embeddings: dict[str, tuple[bytes, int]],
    existing_embeddings: dict[str, tuple[bytes, int]],
    stats: IndexStats,
) -> tuple[list[tuple[int, str]], list[tuple[int, bytes, int]]]:
    """
    Classify chunks as reusable or needing new embeddings.

    Priority: global reuse > local reuse > new embedding.

    Args:
        chunk_hashes: List of text_sha256 hashes.
        normalized_texts: List of normalized chunk texts.
        global_embeddings: Embeddings from other files.
        existing_embeddings: Embeddings from this file's previous version.
        stats: IndexStats to update.

    Returns:
        Tuple of (chunks_to_embed, reusable_indices).
        chunks_to_embed: List of (index, text) needing embedding.
        reusable_indices: List of (index, embedding, dim) to reuse.
    """
    chunks_to_embed = []
    reusable_indices = []

    for i, tsha in enumerate(chunk_hashes):
        if tsha in global_embeddings:
            # Found in another file - reuse with verified integrity
            reusable_indices.append((i, *global_embeddings[tsha]))
            stats.chunks_reused += 1
            stats.chunks_reused_global += 1
        elif tsha in existing_embeddings:
            # Found in this file's previous version
            reusable_indices.append((i, existing_embeddings[tsha][0], existing_embeddings[tsha][1]))
            stats.chunks_reused += 1
            stats.chunks_reused_local += 1
        else:
            # Truly new chunk - needs embedding
            chunks_to_embed.append((i, normalized_texts[i]))
            stats.chunks_embedded += 1

    return chunks_to_embed, reusable_indices


def _store_chunks(
    con,
    file_id: int,
    chunks,
    chunk_hashes: list[str],
    new_embeddings: dict[int, tuple[bytes, int]],
    reusable_indices: list[tuple[int, bytes, int]],
    model: str,
) -> None:
    """
    Store all chunks with embeddings in the database.

    Args:
        con: Database connection.
        file_id: File ID to associate chunks with.
        chunks: List of Chunk objects.
        chunk_hashes: List of text_sha256 hashes.
        new_embeddings: Dict mapping index -> (embedding, dim) for new chunks.
        reusable_indices: List of (index, embedding, dim) for reused chunks.
        model: Embedding model name.
    """
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
    verbose: bool = False,
    ast: bool = False,
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
        verbose: Track and return paths of indexed files (default False).
        ast: Use AST-aware chunking for semantic boundaries (default False).
            Requires: pip install "ogrep[ast]"

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
    stats = IndexStats(indexed_files=[] if verbose else None)

    # Initialize AST chunker if requested
    ast_chunker = None
    if ast:
        ast_chunker = _get_ast_chunker()
        if ast_chunker is None:
            import sys
            print(
                "Warning: AST chunking requested but tree-sitter not available.\n"
                "Install with: pip install 'ogrep[ast]'\n"
                "Falling back to line-based chunking.",
                file=sys.stderr,
            )

    # Load .ogrepignore patterns and combine with CLI excludes
    ignore_patterns = load_ogrepignore(root)
    all_exclude = list(exclude) + ignore_patterns

    con = connect(db_path)

    # Model consistency check - prevent mixing models in the same index
    _check_model_consistency(con, model)

    # Store AST mode in metadata (tracks how index was built)
    from .db import set_metadata
    ast_mode_effective = "true" if (ast and ast_chunker is not None) else "false"
    set_metadata(con, "ast_mode", ast_mode_effective)

    # Get expected dimensions
    expected_dim = _get_expected_dimension(con, model, dimensions)

    # ── Discovery phase: scan filesystem for candidate files ──
    files = list(tqdm(
        iter_files(root, exclude=all_exclude, include=include),
        desc="Scanning",
        unit=" files",
        leave=False,
    ))
    stats.files_scanned = len(files)

    # ── Detection phase: check file types via MIME ──
    detection_results = {}
    if detect and has_file_command() and files:
        with tqdm(total=len(files), desc="Detecting", unit=" files", leave=False) as pbar:
            detection_results = detect_file_types_batch(files, progress_callback=pbar.update)

    for p in tqdm(files, desc="Indexing"):
        # ── Phase 1: File validation and skip checks ──
        b = _read_file_if_indexable(p, max_bytes, detection_results, stats)
        if b is None:
            continue

        st = p.stat()
        sha = _sha256_bytes(b)
        rel = str(p.resolve())

        is_unchanged, existing_row = _is_file_unchanged(con, rel, sha, st.st_mtime_ns, st.st_size)
        if is_unchanged:
            stats.files_skipped += 1
            continue

        # ── Phase 2: Prepare for indexing (read-only DB ops) ──
        stats.files_indexed += 1
        if stats.indexed_files is not None:
            try:
                stats.indexed_files.append(str(p.relative_to(root)))
            except ValueError:
                stats.indexed_files.append(str(p))

        existing_embeddings: dict[str, tuple[bytes, int]] = {}
        if existing_row:
            existing_embeddings = _cache_existing_embeddings(con, int(existing_row[0]))

        # ── Phase 3: Chunk text and compute hashes ──
        text = b.decode("utf-8", errors="ignore")

        # Use AST chunking if available, with fallback to line-based
        if ast_chunker is not None:
            chunks = ast_chunker(
                text,
                filename=str(p),
                max_chunk_lines=chunk_lines,
            )
            # Fall back to line-based if AST produces no chunks (unsupported language)
            if not chunks:
                chunks = chunk_text(text, chunk_size=chunk_lines, overlap=overlap)
        else:
            chunks = chunk_text(text, chunk_size=chunk_lines, overlap=overlap)

        if not chunks:
            continue

        stats.chunks_total += len(chunks)
        chunk_hashes, normalized_texts = _compute_chunk_hashes(chunks)

        # ── Phase 4: Find reusable embeddings (read-only DB ops) ──
        global_embeddings: dict[str, tuple[bytes, int]] = {}
        if expected_dim is not None:
            global_embeddings = _find_global_embeddings(con, chunk_hashes, model, expected_dim)

        chunks_to_embed, reusable_indices = _classify_chunks_for_embedding(
            chunk_hashes, normalized_texts, global_embeddings, existing_embeddings, stats
        )

        # ── Phase 5: Generate new embeddings (API call, outside transaction) ──
        new_embeddings: dict[int, tuple[bytes, int]] = {}
        if chunks_to_embed:
            texts = [t for _, t in chunks_to_embed]
            emb_blobs, dim = embed_texts(texts, model=model, dimensions=dimensions)
            for (idx, _), emb in zip(chunks_to_embed, emb_blobs, strict=True):
                new_embeddings[idx] = (emb, dim)
            if expected_dim is None:
                expected_dim = dim

        # ── Phase 6: Atomic DB write (transaction) ──
        try:
            con.execute("BEGIN IMMEDIATE")
            file_id = _upsert_file_record(con, rel, st.st_mtime_ns, st.st_size, sha, existing_row)
            _store_chunks(con, file_id, chunks, chunk_hashes, new_embeddings, reusable_indices, model)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

    # ── Phase 7: Log history entry (AI tool integration) ──
    # Only log if something was indexed (not just a scan with no changes)
    if stats.files_indexed > 0:
        log_history(
            con,
            action="index",
            files_affected=stats.files_indexed,
            chunks_affected=stats.chunks_total,
            details={
                "files_scanned": stats.files_scanned,
                "files_skipped": stats.files_skipped,
                "chunks_embedded": stats.chunks_embedded,
                "chunks_reused": stats.chunks_reused,
                "indexed_files": stats.indexed_files,
            },
        )

    return stats
