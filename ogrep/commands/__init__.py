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
    - status: Show index status and statistics
    - models: List available embedding models
"""

from __future__ import annotations

from .clean import cmd_clean
from .index import cmd_index
from .models import cmd_models
from .query import cmd_query
from .reindex import cmd_reindex
from .reset import cmd_reset
from .status import cmd_status

__all__ = [
    "cmd_index",
    "cmd_query",
    "cmd_reset",
    "cmd_reindex",
    "cmd_clean",
    "cmd_status",
    "cmd_models",
]
