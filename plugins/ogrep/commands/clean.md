---
description: Remove stale entries from the index (files that no longer exist)
allowed-tools: Bash
---

# ogrep clean

Clean up the index by removing entries for files that have been deleted from the filesystem.

## Usage

```bash
# Clean stale entries (JSON output is default)
ogrep clean

# Clean and compact database
ogrep clean --vacuum

# Clean with human-readable output
ogrep clean --no-json
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--vacuum` | off | Compact the SQLite database after cleaning |
| `--json` | yes | Output as JSON (default for AI/machine use) |
| `--no-json` | - | Output as human-readable text |

## JSON Output

```json
{
  "status": "success",
  "removed_count": 3,
  "removed_paths": [
    "src/deleted_file.py",
    "lib/old_module.py",
    "tests/removed_test.py"
  ],
  "vacuumed": true
}
```

When nothing to clean:

```json
{
  "status": "success",
  "removed_count": 0,
  "removed_paths": [],
  "vacuumed": false
}
```

## Advanced Flags

| Flag | Purpose |
|------|---------|
| `--db PATH` | Explicit SQLite DB path (overrides scope options) |
| `--profile NAME` | Named profile for multiple indexes per repo |
| `--global-cache` | Use `~/.cache/ogrep/<repo_hash>/index.sqlite` |
| `--repo-root PATH` | Explicit repository root |

## When to Use

- After deleting files from the repo
- Before querying to avoid stale results pointing to missing files
- Periodically to keep the index lean
- Use `--vacuum` to reclaim disk space after large cleanups
