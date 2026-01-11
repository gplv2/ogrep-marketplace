"""
Shared utilities for ogrep CLI commands.

This module provides common functionality used across multiple commands,
including database path resolution and argument parsing helpers.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path


def require_embedding_config() -> bool:
    """
    Check if embedding API is configured, print error if not.

    Returns:
        True if configured, False otherwise (with error printed to stderr).
    """
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("OGREP_BASE_URL"):
        return True

    print(
        "Error: No embedding API configured.\n"
        "Set one of:\n"
        "  - OPENAI_API_KEY for OpenAI embeddings\n"
        "  - OGREP_BASE_URL for local embeddings (e.g., http://localhost:1234/v1)",
        file=sys.stderr,
    )
    return False


def _repo_hash(root: Path) -> str:
    """
    Generate a short hash from repository path for global cache keying.

    Args:
        root: The repository root path.

    Returns:
        A 12-character hex string derived from the absolute path.
    """
    return hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12]


def resolve_db_path(
    db_arg: str | None,
    profile: str | None,
    global_cache: bool,
    repo_root: Path | None = None,
) -> Path:
    """
    Resolve the database path based on scope flags.

    Determines the appropriate SQLite database location based on the
    provided scope options. This enables multi-repo setups without
    index pollution between projects.

    Priority (highest to lowest):
        1. Explicit --db path
        2. --global-cache: ~/.cache/ogrep/<repo_hash>/index.sqlite
        3. --profile: .ogrep/<profile>/index.sqlite
        4. Default: .ogrep/index.sqlite

    Args:
        db_arg: Explicit database path from --db flag.
        profile: Profile name from --profile flag.
        global_cache: Whether to use global cache from --global-cache flag.
        repo_root: Repository root path (defaults to current directory).

    Returns:
        Resolved Path to the SQLite database file.

    Examples:
        >>> resolve_db_path(None, None, False)
        PosixPath('.ogrep/index.sqlite')

        >>> resolve_db_path(None, "dev", False)
        PosixPath('.ogrep/dev/index.sqlite')

        >>> resolve_db_path("/custom/path.db", None, False)
        PosixPath('/custom/path.db')
    """
    if db_arg:
        return Path(db_arg)

    root = repo_root or Path.cwd()

    if global_cache:
        cache_dir = Path.home() / ".cache" / "ogrep" / _repo_hash(root)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / "index.sqlite"

    if profile:
        return root / ".ogrep" / profile / "index.sqlite"

    return root / ".ogrep" / "index.sqlite"


def add_scope_args(parser: argparse.ArgumentParser) -> None:
    """
    Add common scope/fencing arguments to an argument parser.

    Adds the standard set of arguments for controlling index scope:
        --db, --profile, --global-cache, --repo-root

    These arguments allow users to manage multiple indexes and prevent
    cross-repository pollution in monorepo or multi-project setups.

    Args:
        parser: The argparse parser or subparser to add arguments to.
    """
    parser.add_argument(
        "--db",
        default=None,
        help="Explicit SQLite DB path (overrides all other scope options)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Profile name for multiple indexes per repo (.ogrep/<profile>/index.sqlite)",
    )
    parser.add_argument(
        "--global-cache",
        action="store_true",
        help="Use global cache at ~/.cache/ogrep/<repo_hash>/index.sqlite",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Explicit repository root (default: current directory)",
    )


# Extension to programming language mapping
EXTENSION_LANGUAGES: dict[str, str] = {
    # Python
    ".py": "python",
    ".pyi": "python",
    ".pyx": "python",
    # JavaScript/TypeScript
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    # Web
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    # Systems languages
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".zig": "zig",
    # JVM
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".groovy": "groovy",
    # .NET
    ".cs": "csharp",
    ".fs": "fsharp",
    ".vb": "vb",
    # Scripting
    ".rb": "ruby",
    ".php": "php",
    ".pl": "perl",
    ".pm": "perl",
    ".lua": "lua",
    ".r": "r",
    ".R": "r",
    # Shell
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".fish": "shell",
    ".ps1": "powershell",
    ".psm1": "powershell",
    # Functional
    ".hs": "haskell",
    ".lhs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hrl": "erlang",
    # Data/Config (included for completeness, often excluded from indexing)
    ".sql": "sql",
    ".graphql": "graphql",
    ".gql": "graphql",
    # Swift/Objective-C
    ".swift": "swift",
    ".m": "objective-c",
    ".mm": "objective-cpp",
    # Other
    ".vim": "vim",
    ".el": "elisp",
    ".rkt": "racket",
    ".nim": "nim",
    ".d": "d",
    ".dart": "dart",
    ".v": "v",
    ".asm": "assembly",
    ".s": "assembly",
    ".S": "assembly",
    ".wasm": "wasm",
    ".wat": "wasm",
}


def detect_language(path: str) -> str | None:
    """
    Detect programming language from file extension.

    Args:
        path: File path (absolute or relative).

    Returns:
        Language name (lowercase) or None if unknown.

    Example:
        >>> detect_language("/home/user/project/auth.py")
        'python'
        >>> detect_language("main.rs")
        'rust'
        >>> detect_language("Makefile")
        None
    """
    ext = Path(path).suffix.lower()
    # Handle uppercase extensions like .R
    if ext not in EXTENSION_LANGUAGES:
        ext = Path(path).suffix  # Try original case
    return EXTENSION_LANGUAGES.get(ext)
