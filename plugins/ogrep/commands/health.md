---
description: Show database health diagnostics and repair options
allowed-tools: Bash
argument-hint: [--vacuum] [--rebuild-fts] [--integrity] [--full] [--json]
---

Display comprehensive database diagnostics including table sizes, indexes, SQLite info, FTS5 stats, and integrity checks.

## Commands

```bash
# Full diagnostic output
ogrep health

# With JSON output (for AI tool integration)
ogrep health --json
```

## Repair Options

| Flag | Description |
|------|-------------|
| `--vacuum` | Reclaim space and defragment database |
| `--rebuild-fts` | Drop and rebuild FTS5 full-text index |
| `--integrity` | Run full integrity check (slow on large DBs) |
| `--full` | All repairs: vacuum + rebuild-fts + integrity |
| `--json` | Output results as JSON |

## JSON Output

```json
{
  "database": "/path/to/.ogrep/index.sqlite",
  "tables": {
    "chunks": {"rows": 217, "size_bytes": 1782579},
    "files": {"rows": 42, "size_bytes": 8192}
  },
  "dedup_stats": {
    "total_chunks": 217,
    "unique_hashes": 200,
    "duplicates": 17,
    "savings_percent": 7.8
  },
  "fts5": {"rows": 217, "tokens_estimate": 54073},
  "sqlite_info": {"version": "3.45.0", "page_size": 4096},
  "integrity": "ok",
  "operations": {"vacuum": true, "rebuild_fts": false}
}
```
