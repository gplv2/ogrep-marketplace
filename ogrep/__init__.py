"""
ogrep - Local semantic grep powered by SQLite and OpenAI embeddings.

Search your codebase by meaning, not just keywords. ogrep indexes your
source files into a local SQLite database and uses OpenAI's embedding
API to enable semantic search.

Basic Usage:
    CLI:
        $ ogrep index .
        $ ogrep query "where is authentication handled?"

    Python API:
        >>> from ogrep import index_path, query
        >>> from pathlib import Path
        >>> index_path(Path("."), Path(".ogrep/index.sqlite"))
        >>> hits = query(Path(".ogrep/index.sqlite"), "database connection")
        >>> for h in hits:
        ...     print(f"{h.path}:{h.start_line}")

Modules:
    indexer: File scanning and embedding generation
    search: Semantic query functionality
    chunking: Text splitting with overlap
    db: SQLite database management
    embed: OpenAI embedding API wrapper
    commands: CLI command implementations
"""

from .chunking import Chunk, chunk_lines
from .db import connect
from .embed import embed_texts
from .filetype import (
    FileTypeResult,
    detect_file_types_batch,
    has_file_command,
)
from .indexer import DEFAULT_EXCLUDES, index_path, iter_files, load_ogrepignore
from .models import (
    DEFAULT_CHUNK_LINES,
    DEFAULT_MODEL,
    DEFAULT_OVERLAP_LINES,
    MODELS,
    EmbeddingModel,
    get_model,
    get_optimal_chunk_lines,
    get_optimal_overlap,
    list_models,
    resolve_model,
)
from .search import Hit, query

__version__ = "0.7.1"

__all__ = [
    "__version__",
    # Core functions
    "index_path",
    "query",
    "iter_files",
    "load_ogrepignore",
    "embed_texts",
    "connect",
    "chunk_lines",
    # File type detection
    "detect_file_types_batch",
    "has_file_command",
    "FileTypeResult",
    # Constants
    "DEFAULT_EXCLUDES",
    # Model utilities
    "resolve_model",
    "get_model",
    "get_optimal_chunk_lines",
    "get_optimal_overlap",
    "list_models",
    "MODELS",
    "DEFAULT_MODEL",
    "DEFAULT_CHUNK_LINES",
    "DEFAULT_OVERLAP_LINES",
    # Data classes
    "Hit",
    "Chunk",
    "EmbeddingModel",
]
