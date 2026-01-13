"""
CLI command implementations for ogrep.

This module provides the individual command handlers for the ogrep CLI.
Each command is implemented in its own submodule for maintainability.

Commands:
    - index: Index a directory for semantic search
    - query: Run semantic queries against the index
    - reset: Remove the index database
    - reindex: Force rebuild the index from scratch
    - clean: Remove stale entries from the index
    - delete: Remove specific files from the index
    - log: Show index change history (AI tool integration)
    - status: Show index status and statistics
    - models: List available embedding models
    - tune: Auto-tune chunk size for optimal relevance
    - benchmark: Compare all embedding models
"""

from __future__ import annotations

from .benchmark import cmd_benchmark
from .chunk import cmd_chunk
from .clean import cmd_clean
from .delete import cmd_delete
from .health import cmd_health
from .index import cmd_index
from .log import cmd_log
from .models import cmd_models
from .query import cmd_query
from .reindex import cmd_reindex
from .reset import cmd_reset
from .status import cmd_status
from .tune import cmd_tune

__all__ = [
    "cmd_benchmark",
    "cmd_chunk",
    "cmd_clean",
    "cmd_delete",
    "cmd_health",
    "cmd_index",
    "cmd_log",
    "cmd_models",
    "cmd_query",
    "cmd_reindex",
    "cmd_reset",
    "cmd_status",
    "cmd_tune",
]
