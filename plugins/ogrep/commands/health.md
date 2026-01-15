---
description: Show database health diagnostics and repair options
allowed-tools: Bash
---

# ogrep health

Display comprehensive database diagnostics including table sizes, indexes, SQLite info, FTS5 stats, and integrity checks. Supports repair operations via flags.

## Usage

```bash
# Full diagnostic output (JSON is default)
ogrep health

# With human-readable output
ogrep health --no-json

# Run all safe repairs
ogrep health --full

# Just reclaim space
ogrep health --vacuum
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | yes | Output as JSON (default for AI/machine use) |
| `--no-json` | - | Output as human-readable text |

## Repair Options

| Flag | Description |
|------|-------------|
| `--vacuum` | Reclaim space and defragment database |
| `--rebuild-fts` | Drop and rebuild FTS5 full-text index |
| `--integrity` | Run full integrity check (slow on large DBs) |
| `--full` | All safe repairs: vacuum + rebuild-fts + integrity (does NOT include reindex) |
| `--reindex` | Show reindex command (does not run automatically - requires re-embedding) |

**Note:** `--reindex` only shows the command to run, it doesn't execute it because reindexing requires embedding API calls.

## JSON Output

```json
{
  "database": ".ogrep/index.sqlite",
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

## Key Fields

| Field | Description |
|-------|-------------|
| `tables` | Row counts and sizes for each table |
| `dedup_stats` | Chunk deduplication efficiency |
| `fts5` | Full-text search index stats |
| `integrity` | `"ok"` or error details |
| `operations` | Which repair operations were run |

## Advanced Flags

| Flag | Purpose |
|------|---------|
| `--db PATH` | Explicit SQLite DB path (overrides scope options) |
| `--profile NAME` | Named profile for multiple indexes per repo |
| `--global-cache` | Use `~/.cache/ogrep/<repo_hash>/index.sqlite` |
| `--repo-root PATH` | Explicit repository root |

## When to Use

- **After disk issues** - check integrity and vacuum
- **Slow queries** - rebuild FTS index
- **Large database** - vacuum to reclaim space
- **Troubleshooting** - full diagnostics to understand index state
