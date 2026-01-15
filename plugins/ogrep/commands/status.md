---
description: Show ogrep index status and statistics
allowed-tools: Bash
argument-hint: [--no-json]
---

Display information about the current index including file count, chunk count, model used, and database size.

## Commands

```bash
# Show status (JSON is default)
ogrep status

# Show status as human-readable text
ogrep status --no-json
```

## JSON Output

JSON is the default output format:

```json
{
  "database": "/path/to/.ogrep/index.sqlite",
  "status": "indexed",
  "indexed": true,
  "branch": "main",
  "branch_files": 42,
  "files": 42,
  "branches": {"main": 42},
  "chunks": 217,
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "size_bytes": 1048576,
  "size_human": "1.0 MB"
}
```

**Branch fields:**
- `branch`: Current git branch name (or "default" if not in a git repo)
- `branch_files`: Number of files indexed on the current branch
- `branches`: Map of all indexed branches to their file counts

If no index exists:

```json
{
  "database": "/path/to/.ogrep/index.sqlite",
  "status": "not_indexed",
  "indexed": false,
  "message": "No index found at ..."
}
```
