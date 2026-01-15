---
description: Force rebuild of the semantic search index from scratch
allowed-tools: Bash
argument-hint: [path] [--no-json]
---

Completely rebuild the index by removing it and reindexing from scratch.

## Commands

```bash
# Rebuild index for current directory (JSON output is default)
ogrep reindex ${1:-.}

# Rebuild with human-readable output
ogrep reindex ${1:-.} --no-json
```

## Flags

| Flag | Description |
|------|-------------|
| `--no-json` | Output as human-readable text instead of JSON (default is JSON) |
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
