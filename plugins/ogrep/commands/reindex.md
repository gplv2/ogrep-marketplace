---
description: Force rebuild of the semantic search index from scratch
allowed-tools: Bash
argument-hint: [path]
---

# ogrep reindex

Remove existing index and rebuild completely. Use this to change indexing options (like enabling AST chunking) or to fix a corrupted index.

## Usage

```bash
# Rebuild index for current directory
ogrep reindex .

# Rebuild with AST-aware chunking (recommended)
ogrep reindex . --ast

# Rebuild with different model
ogrep reindex . -m nomic

# Rebuild with human-readable output
ogrep reindex . --no-json
```

## Core Flags

| Flag | Alias | Default | Description |
|------|-------|---------|-------------|
| `--ast` | - | off | Use AST-aware chunking (by function/class, not lines) |
| `--json` | - | yes | Output as JSON (default for AI/machine use) |
| `--no-json` | - | - | Output as human-readable text |

## Model & Chunking Flags

| Flag | Alias | Default | Description |
|------|-------|---------|-------------|
| `--model` | `-m` | `text-embedding-3-small` | Embedding model or alias: `small`, `large`, `ada`, `nomic`, `bge` |
| `--dimensions` | `-d` | model default | Embedding dimensions |
| `--chunk-lines` | - | model-specific | Lines per chunk (e.g., 60 for OpenAI, 30 for nomic) |
| `--overlap` | - | model-specific | Overlapping lines between chunks |
| `--max-bytes` | - | 2MB | Max file size in bytes |

## File Selection Flags

| Flag | Alias | Description |
|------|-------|-------------|
| `--exclude PATTERN` | `-e` | Add exclude patterns (added to defaults) |
| `--include PATTERN` | `-i` | Include patterns (override default excludes, e.g., `-i '*.md'`) |

## JSON Output

```json
{
  "status": "success",
  "path": "/path/to/repo",
  "database": ".ogrep/index.sqlite",
  "files_indexed": 42,
  "files_skipped": 5,
  "chunks_total": 217,
  "chunks_embedded": 217,
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "ast_mode": true
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

- **Enable AST chunking** on an existing index: `ogrep reindex . --ast`
- **Change embedding model** - must reindex to switch models
- **Fix corrupted index** - full rebuild from scratch
- **Change chunk size** - after tuning with `ogrep tune`

## Notes

- This is equivalent to `ogrep reset --force && ogrep index .`
- **All existing embeddings are discarded** - will re-embed everything
- Use `ogrep index .` for incremental updates (faster, cheaper)
- Check `ogrep status` to see current index settings before rebuilding
