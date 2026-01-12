---
description: Index the current repository for semantic search (creates .ogrep/index.sqlite)
allowed-tools: Bash
argument-hint: [path] [--list] [--no-detect] [--json]
---

Run indexing with ogrep. If no path is provided, index the current directory.

## Commands

```bash
# Index current directory
ogrep index ${1:-.}

# Preview files before indexing (recommended for new repos)
ogrep index ${1:-.} --list

# Index without MIME detection (faster)
ogrep index ${1:-.} --no-detect

# Index with JSON output (for AI tool integration)
ogrep index ${1:-.} --json
```

## Flags

| Flag | Description |
|------|-------------|
| `--list`, `-l` | Preview files with detection results (dry run) |
| `--no-detect` | Disable MIME type detection (faster, null-byte only) |
| `--json` | Output results as JSON (structured metadata) |
| `-e PATTERN` | Add exclude patterns |
| `-i PATTERN` | Include patterns (override excludes) |

## JSON Output

When using `--json`, returns structured data:

```json
{
  "status": "success",
  "path": "/path/to/repo",
  "files_indexed": 42,
  "files_skipped": 5,
  "chunks_total": 217,
  "chunks_reused": 150,
  "chunks_embedded": 67,
  "tokens_saved_estimate": 15000,
  "model": "text-embedding-3-small",
  "dimensions": 1536
}
```

## Notes

- Use `--list` first to see what will be indexed
- Create `.ogrepignore` for permanent exclusions
- Binary files are auto-detected and excluded
- YAML files (*.yaml, *.yml) are now indexed by default

If `ogrep` is not installed, run: `pip install ogrep`
