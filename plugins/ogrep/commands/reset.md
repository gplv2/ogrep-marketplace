---
description: Remove the ogrep index database for the current scope
allowed-tools: Bash
argument-hint: [--force] [--all] [--no-json]
---

Remove the semantic search index.

## Commands

```bash
# Reset current branch only (requires -f in non-interactive mode)
ogrep reset -f

# Reset entire database (all branches)
ogrep reset -f --all

# Reset with human-readable output
ogrep reset -f --no-json
```

## Flags

| Flag | Description |
|------|-------------|
| `-f`, `--force` | Skip confirmation (required in non-interactive mode) |
| `--all` | Delete entire database (all branches). Without this, only current branch is cleared |
| `--no-json` | Output as human-readable text instead of JSON (default is JSON) |

## Branch-Aware Behavior

By default, `ogrep reset -f` clears only the current git branch from the index:
- Files indexed on the current branch are removed
- Files indexed on other branches are preserved
- Shared embeddings (chunks) remain available for other branches

Use `--all` to delete the entire database including all branches.

## JSON Output

```json
{
  "status": "success",
  "database": "/path/to/.ogrep/index.sqlite",
  "removed": true,
  "branch": "main",
  "files_removed": 42,
  "size_bytes": 1048576,
  "size_human": "1.0 MB"
}
```

The `-f` flag is required in non-interactive mode (like Claude Code).
