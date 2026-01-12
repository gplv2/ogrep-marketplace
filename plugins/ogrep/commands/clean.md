---
description: Remove stale entries from the index (files that no longer exist)
allowed-tools: Bash
argument-hint: [--vacuum] [--json]
---

Clean up the index by removing entries for files that have been deleted.

## Commands

```bash
# Clean stale entries
ogrep clean

# Clean and compact database
ogrep clean --vacuum

# Clean with JSON output
ogrep clean --json
```

## Flags

| Flag | Description |
|------|-------------|
| `--vacuum` | Compact the SQLite database after cleaning |
| `--json` | Output results as JSON |

## JSON Output

```json
{
  "status": "success",
  "removed_count": 3,
  "removed_paths": ["/path/to/deleted1.py", "/path/to/deleted2.py"],
  "vacuumed": true
}
```
