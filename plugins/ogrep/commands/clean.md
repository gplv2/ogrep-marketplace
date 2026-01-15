---
description: Remove stale entries from the index (files that no longer exist)
allowed-tools: Bash
argument-hint: [--vacuum] [--no-json]
---

Clean up the index by removing entries for files that have been deleted and pruning deleted git branches.

## Commands

```bash
# Clean stale entries (JSON output is default)
ogrep clean

# Clean and compact database
ogrep clean --vacuum

# Clean with human-readable output
ogrep clean --no-json
```

## Flags

| Flag | Description |
|------|-------------|
| `--vacuum` | Compact the SQLite database after cleaning |
| `--no-json` | Output as human-readable text instead of JSON (default is JSON) |

## Branch Pruning

The clean command automatically detects and removes entries for git branches that no longer exist:

- Queries indexed branches from the database
- Compares against current git branches
- Removes file entries for deleted branches
- Shared embeddings (chunks) are preserved if used by other branches

This is especially useful after merging and deleting feature branches.

## JSON Output

```json
{
  "status": "success",
  "removed_count": 3,
  "removed_paths": ["/path/to/deleted1.py", "/path/to/deleted2.py"],
  "pruned_branches": ["feature/old-auth"],
  "pruned_files": 15,
  "vacuumed": true
}
```
