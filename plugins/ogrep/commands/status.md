---
description: Show ogrep index status and statistics
allowed-tools: Bash
argument-hint: [--json]
---

Display information about the current index including file count, chunk count, model used, and database size.

## Commands

```bash
# Show status (human readable)
ogrep status

# Show status as JSON (for AI tool integration)
ogrep status --json
```

## JSON Output

When using `--json`, returns structured data:

```json
{
  "database": "/path/to/.ogrep/index.sqlite",
  "status": "indexed",
  "indexed": true,
  "files": 42,
  "chunks": 217,
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "size_bytes": 1048576,
  "size_human": "1.0 MB"
}
```

If no index exists:

```json
{
  "database": "/path/to/.ogrep/index.sqlite",
  "status": "not_indexed",
  "indexed": false,
  "message": "No index found at ..."
}
```
