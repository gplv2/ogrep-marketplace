---
description: Refresh the index by reindexing any files that have changed since last index
allowed-tools: Bash
---

Run:
- `ogrep index .`

This performs an incremental reindex - only changed files are re-embedded,
and unchanged chunks reuse their existing embeddings (fast and token-efficient).

Use this before running multiple queries to ensure all results are fresh,
or configure Claude Code hooks to auto-refresh after file edits.
