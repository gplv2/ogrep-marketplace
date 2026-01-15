---
description: Remove the ogrep index database for the current scope
allowed-tools: Bash
---

# ogrep reset

Delete the semantic search index database. **Destructive operation** - requires `--force` flag.

## Usage

```bash
# Reset index (requires -f in non-interactive mode)
ogrep reset -f

# Reset with human-readable output
ogrep reset -f --no-json
```

## Options

| Flag | Alias | Default | Description |
|------|-------|---------|-------------|
| `--force` | `-f` | - | Skip confirmation prompt (required in non-interactive mode) |
| `--json` | - | yes | Output as JSON (default for AI/machine use) |
| `--no-json` | - | - | Output as human-readable text |

## JSON Output

```json
{
  "status": "success",
  "database": ".ogrep/index.sqlite",
  "removed": true,
  "size_bytes": 1048576,
  "size_human": "1.0 MB"
}
```

If no index exists:

```json
{
  "status": "not_found",
  "database": ".ogrep/index.sqlite",
  "removed": false,
  "message": "No index found at this location"
}
```

## Advanced Flags

| Flag | Purpose |
|------|---------|
| `--db PATH` | Explicit SQLite DB path (overrides scope options) |
| `--profile NAME` | Named profile for multiple indexes per repo |
| `--global-cache` | Use `~/.cache/ogrep/<repo_hash>/index.sqlite` |
| `--repo-root PATH` | Explicit repository root |

## Notes

- **`-f` is required** when running from Claude Code or scripts (non-interactive)
- This completely removes the index - you'll need to run `ogrep index .` again
- To rebuild with different settings (e.g., add AST), use `ogrep reindex . --ast` instead
