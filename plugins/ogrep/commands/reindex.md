---
description: Force rebuild of the semantic search index from scratch
allowed-tools: Bash
argument-hint: [path] [--json]
---

Completely rebuild the index by removing it and reindexing from scratch.

## Commands

```bash
# Rebuild index for current directory
ogrep reindex ${1:-.}

# Rebuild with JSON output
ogrep reindex ${1:-.} --json
```

## Flags

| Flag | Description |
|------|-------------|
| `--json` | Output results as JSON |
| `-m MODEL` | Use specific embedding model |
| `--chunk-lines N` | Lines per chunk (default: 60) |
| `--overlap N` | Overlap lines between chunks (default: 10) |

## JSON Output

```json
{
  "status": "success",
  "path": "/path/to/repo",
  "files_indexed": 42,
  "files_skipped": 5,
  "chunks_total": 217,
  "chunks_embedded": 217,
  "model": "text-embedding-3-small",
  "dimensions": 1536
}
```

This is equivalent to `ogrep reset --force && ogrep index`.
