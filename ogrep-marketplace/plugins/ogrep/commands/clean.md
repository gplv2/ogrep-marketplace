---
description: Remove stale entries from the index (files that no longer exist)
allowed-tools: Bash
argument-hint: [--vacuum]
---

Clean up the index by removing entries for files that have been deleted.

Run:
- `ogrep clean $ARGUMENTS`

Use `--vacuum` to also compact the SQLite database after cleaning.
