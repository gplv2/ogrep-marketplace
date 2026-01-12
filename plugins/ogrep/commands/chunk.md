---
name: chunk
description: Get a chunk by reference with optional context. Use after query finds something interesting to expand context.
---

# ogrep chunk

Retrieve chunks by reference (path:index) or raw ID, with optional neighboring chunks for context.

## Usage

```bash
ogrep chunk "path/to/file.py:N"     # By chunk reference
ogrep chunk 42                       # By raw chunk ID

# With context
ogrep chunk "auth.py:2" --before 1   # + 1 chunk before
ogrep chunk "auth.py:2" --after 1    # + 1 chunk after
ogrep chunk "auth.py:2" --context 1  # + 1 before AND after
```

## Options

| Flag | Short | Description |
|------|-------|-------------|
| `--before N` | `-B` | Include N chunks before the requested chunk |
| `--after N` | `-A` | Include N chunks after the requested chunk |
| `--context N` | `-C` | Include N chunks before AND after (shorthand) |
| `--json` | | Output as JSON (default, included for consistency) |

## Output Format

Returns JSON with the requested chunk and any context:

```json
{
  "requested": {
    "chunk_ref": "src/auth.py:2",
    "chunk_id": 42,
    "chunk_index": 2,
    "path": "/home/user/repo/src/auth.py",
    "relative_path": "src/auth.py",
    "start_line": 61,
    "end_line": 120,
    "language": "python",
    "text": "def authenticate_user(...):\n    ..."
  },
  "before": [
    {
      "chunk_ref": "src/auth.py:1",
      "chunk_id": 41,
      "start_line": 1,
      "end_line": 60,
      "text": "import hashlib\n..."
    }
  ],
  "after": []
}
```

## Common Patterns

### Expand Context After Query

```bash
# Query found something interesting
ogrep query "database connection" --json
# Result: chunk_ref: "db.py:3"

# Get context above (imports, setup)
ogrep chunk "db.py:3" --before 1
```

### Trace Code Flow

```bash
# See what comes after a function definition
ogrep chunk "handler.py:2" --after 2
```

### Full Section Context

```bash
# Get surrounding context
ogrep chunk "auth.py:4" --context 1
```
