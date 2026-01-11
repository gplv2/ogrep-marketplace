---
description: Index the current repository for semantic search (creates .ogrep/index.sqlite)
allowed-tools: Bash
argument-hint: [path] [--list] [--no-detect]
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
```

## Flags

| Flag | Description |
|------|-------------|
| `--list`, `-l` | Preview files with detection results (dry run) |
| `--no-detect` | Disable MIME type detection (faster, null-byte only) |
| `-e PATTERN` | Add exclude patterns |
| `-i PATTERN` | Include patterns (override excludes) |

## Notes

- Use `--list` first to see what will be indexed
- Create `.ogrepignore` for permanent exclusions
- Binary files are auto-detected and excluded

If `ogrep` is not installed, run: `pip install ogrep`
