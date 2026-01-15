---
description: Index the current repository for semantic search (creates .ogrep/index.sqlite)
allowed-tools: Bash
argument-hint: [path]
---

# ogrep index

Scan files, generate embeddings, and store in local SQLite database.

## Usage

```bash
# Index current directory (JSON output is default)
ogrep index .

# Preview files before indexing (recommended for new repos)
ogrep index . --list

# Index with AST-aware chunking (recommended for code)
ogrep index . --ast

# Index with human-readable output
ogrep index . --no-json

# Index with verbose output (see files being processed)
ogrep index . --verbose
```

## Core Flags

| Flag | Alias | Default | Description |
|------|-------|---------|-------------|
| `--list` | `-l` | - | Preview files with detection results (dry run) |
| `--ast` | - | off | Use AST-aware chunking (by function/class, not lines) |
| `--verbose` | `-v` | off | Show files being indexed |
| `--json` | - | yes | Output as JSON (default for AI/machine use) |
| `--no-json` | - | - | Output as human-readable text |
| `--no-detect` | - | - | Disable MIME type detection (faster, null-byte only) |

## File Selection Flags

| Flag | Alias | Description |
|------|-------|-------------|
| `--exclude PATTERN` | `-e` | Add exclude patterns (added to defaults) |
| `--include PATTERN` | `-i` | Include patterns (override default excludes, e.g., `-i '*.md'`) |
| `--max-bytes N` | - | Max file size in bytes (default: 2MB) |

## Model & Chunking Flags

| Flag | Alias | Default | Description |
|------|-------|---------|-------------|
| `--model` | `-m` | `text-embedding-3-small` | Embedding model or alias: `small`, `large`, `ada`, `nomic`, `bge` |
| `--dimensions` | `-d` | model default | Embedding dimensions |
| `--chunk-lines` | - | model-specific | Lines per chunk (e.g., 60 for OpenAI, 30 for nomic) |
| `--overlap` | - | model-specific | Overlapping lines between chunks |

## AST-Aware Chunking

Instead of splitting by arbitrary line counts, AST chunking respects function, class, and method boundaries:

```bash
# Install AST support first
pip install "ogrep[ast]"

# Index with AST chunking
ogrep index . --ast
```

**Benefits:**
- Functions/classes stay intact (not split mid-method)
- Better semantic search accuracy for code
- Chunks align with logical code boundaries

**Supported languages:** Python, JavaScript, TypeScript, Go, Rust (core), plus Ruby, Java, C, C++, C#, Bash with `ogrep[ast-all]`

## JSON Output

```json
{
  "status": "success",
  "path": "/path/to/repo",
  "database": ".ogrep/index.sqlite",
  "files_indexed": 42,
  "files_skipped": 5,
  "chunks_total": 217,
  "chunks_reused": 150,
  "chunks_embedded": 67,
  "tokens_saved_estimate": 15000,
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

## Notes

- **Use `--list` first** to see what will be indexed before committing
- **Use `--ast`** for codebases (better search accuracy)
- Create `.ogrepignore` for permanent exclusions (like `.gitignore` syntax)
- Binary files are auto-detected and excluded
- Unchanged files are skipped (chunks reused to save API costs)

**If `ogrep` is not installed:**
```bash
pip install ogrep              # Basic
pip install "ogrep[ast]"       # With AST support
pip install "ogrep[ast,rerank]" # With AST + reranking
```
