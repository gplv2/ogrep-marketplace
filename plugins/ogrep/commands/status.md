---
description: Show ogrep index status and statistics
allowed-tools: Bash
---

# ogrep status

Display information about the current index including file count, chunk count, model used, AST mode, and database size.

## Usage

```bash
# Show status (JSON is default)
ogrep status

# Show status as human-readable text
ogrep status --no-json
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | yes | Output as JSON (default for AI/machine use) |
| `--no-json` | - | Output as human-readable text |

## JSON Output

When index exists:

```json
{
  "database": ".ogrep/index.sqlite",
  "status": "indexed",
  "indexed": true,
  "files": 42,
  "chunks": 217,
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "ast_mode": true,
  "size_bytes": 1048576,
  "size_human": "1.0 MB"
}
```

When no index exists:

```json
{
  "database": ".ogrep/index.sqlite",
  "status": "not_indexed",
  "indexed": false,
  "message": "No index found. Run: ogrep index ."
}
```

## Key Fields

| Field | Description |
|-------|-------------|
| `indexed` | Boolean - quick check if index exists |
| `files` | Number of files in the index |
| `chunks` | Total chunks (what queries search over) |
| `model` | Embedding model used (queries must match) |
| `ast_mode` | Whether AST-aware chunking was used |
| `size_human` | Human-readable database size |

## Advanced Flags

| Flag | Purpose |
|------|---------|
| `--db PATH` | Explicit SQLite DB path (overrides scope options) |
| `--profile NAME` | Named profile for multiple indexes per repo |
| `--global-cache` | Use `~/.cache/ogrep/<repo_hash>/index.sqlite` |
| `--repo-root PATH` | Explicit repository root |

## Notes

- Check `ast_mode` - if `false`, consider `ogrep reindex . --ast` for better accuracy
- The `model` must match between index and query
- Use before querying to verify index exists and is up to date
