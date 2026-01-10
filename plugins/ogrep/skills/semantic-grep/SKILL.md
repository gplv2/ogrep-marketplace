---
name: semantic-grep
description: Semantic grep for a repo. Use when the user asks to "search by meaning", "find where this is implemented", "grep semantically", "where is this handled", or when exact grep is not enough.
allowed-tools: Bash, Read
---

# Semantic grep workflow (ogrep)

Fast semantic search over local repos using `ogrep` (SQLite index + OpenAI embeddings).

## Quick Start

```bash
# Index the repo (run once, or after major changes)
ogrep index .

# Semantic search
ogrep query "where is authentication handled?" -n 15
```

## Smart Defaults

**Source-only indexing** - By default, ogrep indexes only source code:
- Excludes: `*.md`, `*.json`, `*.yaml`, `*.toml`, `docs/*`, `vendor/*`, etc.
- Skips: `.git/`, `node_modules/`, `.venv/`, `__pycache__/`

**Optimal chunk size** - 60 lines with 10-line overlap (tested for best relevance).

## Commands

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index current directory |
| `ogrep query "text" -n 15` | Semantic search |
| `ogrep status` | Show index info |
| `ogrep reset -f` | Delete index |
| `ogrep models` | List embedding models |

## Override Defaults

```bash
# Include markdown files (normally excluded)
ogrep index . -i '*.md'

# Add extra exclusions
ogrep index . -e 'test_*' -e 'fixtures/*'

# Use high-accuracy model (slower, more expensive)
ogrep index . -m large
```

## Operational Notes

- Requires `OPENAI_API_KEY` in environment
- Model must match between index and query (use same `-m` flag)
- Run `ogrep status` to check current index model
