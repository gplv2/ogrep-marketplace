---
description: Remove the ogrep index database for the current scope
allowed-tools: Bash
argument-hint: [--force] [--no-json]
---

Remove the semantic search index.

## Commands

```bash
# Reset index (requires -f in non-interactive mode)
ogrep reset -f

# Reset with human-readable output
ogrep reset -f --no-json
```

## Flags

| Flag | Description |
|------|-------------|
| `-f`, `--force` | Skip confirmation (required in non-interactive mode) |
| `--no-json` | Output as human-readable text instead of JSON (default is JSON) |

## JSON Output

```json
{
  "status": "success",
  "database": "/path/to/.ogrep/index.sqlite",
  "removed": true,
  "size_bytes": 1048576,
  "size_human": "1.0 MB"
}
```

The `-f` flag is required in non-interactive mode (like Claude Code).
