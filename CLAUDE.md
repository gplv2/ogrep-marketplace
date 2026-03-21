# CLAUDE.md - ogrep Developer Guide

## Overview

**ogrep** is a local semantic grep tool: SQLite index + OpenAI/local embeddings + FTS5 hybrid search + branch-aware indexing.

## Claude Code Environment Setup

**Critical:** Claude Code runs bash commands in a non-interactive shell. Environment variables from `.bashrc`, `.zshrc`, or `direnv` are **NOT automatically loaded**.

### Configure API Keys

Create `.claude/settings.local.json` in your project:

```bash
# Option 1: Copy from template
cp .claude/settings.json.example .claude/settings.local.json
# Then edit with your actual keys

# Option 2: Generate from current shell (run in terminal where env is loaded)
cat << EOF > .claude/settings.local.json
{
  "env": {
    "VOYAGE_API_KEY": "$VOYAGE_API_KEY",
    "OPENAI_API_KEY": "$OPENAI_API_KEY"
  }
}
EOF
```

Or configure globally in `~/.claude/settings.json` for all projects.

### Settings Template

See `.claude/settings.json.example` for all available settings. Convention:
- Keys starting with `_` are disabled (e.g., `_OGREP_MODEL`)
- Remove the `_` prefix to enable a setting

### Why This Matters

Without this configuration, Claude Code cannot run `ogrep` commands that require API access. You'll see authentication errors even if your terminal has the env vars set.

## CLI Quick Reference

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index directory (AST chunking when available) |
| `ogrep index . --no-ast` | Index with line-based chunking |
| `ogrep index . --list` | Preview files to be indexed |
| `ogrep query "text"` | Search (auto-refreshes stale files) |
| `ogrep query "text" -M hybrid` | Hybrid search (default) |
| `ogrep query "text" --rerank` | Cross-encoder reranking |
| `ogrep query "text" -g "*.py"` | Filter to Python files |
| `ogrep query "text" --summarize` | File-level summary (token-efficient) |
| `ogrep query "text" --branch main` | Query specific branch |
| `ogrep chunk "path:N" -C 1` | Get chunk with context |
| `ogrep status` | Index stats |
| `ogrep health` | Full diagnostics |
| `ogrep reset -f` | Clear current branch |
| `ogrep reset -f --all` | Clear entire index |
| `ogrep reindex .` | Rebuild index |
| `ogrep clean --vacuum` | Remove stale entries |
| `ogrep models` | List available models |
| `ogrep device` | Check GPU/CPU |
| `ogrep tune .` | Auto-tune chunk size (uses AST when available) |
| `ogrep benchmark .` | Run quality benchmarks |
| `ogrep cache-report` | Show embedding cache stats |
| `ogrep delete "file"` | Delete specific file from index |
| `ogrep log` | Show indexing log |

**JSON output is default.** Use `--no-json` for human-readable.

## Reranking

**Key rule:** Reranking **helps weak embeddings** but **hurts strong embeddings** (benchmark: `test-reports/BENCHMARK-REPORT-2026-01-16.md`).

- **OpenAI embeddings** (MRR 0.700): Don't rerank (-21% with flashrank)
- **Local/Nomic embeddings** (MRR 0.545→0.633): Use `--rerank` (+16% with flashrank)

| Model | Backend | Size | Context | Install | Parallel-safe |
|-------|---------|------|---------|---------|---------------|
| `flashrank` (default) | ONNX | ~4MB | 512 | `[rerank-light]` | Yes |
| `flashrank:mini` | ONNX | ~50MB | 512 | `[rerank-light]` | Yes |
| `voyage` | Voyage AI API | - | 32K | `[voyage]` | Yes |
| `voyage:lite` | Voyage AI API | - | 32K | `[voyage]` | Yes |
| `minilm` | sentence-transformers | ~90MB | 512 | `[rerank]` | No (file lock) |
| `bge-m3` | sentence-transformers | ~300MB | 8K | `[rerank]` | No (file lock) |

**Note:** `--rerank-top` must be >= `-n`. Sentence-transformers lock timeout configurable via `OGREP_RERANK_LOCK_TIMEOUT` (default: 120s).

## Branch-Aware Indexing

Embeddings are content-addressed (`text_sha256`). Same code = same embedding regardless of branch. Switching branches only embeds genuinely new code.

```bash
ogrep status                    # Shows branch info
ogrep query "x" --branch main   # Query specific branch
ogrep reset -f                  # Clear current branch only
ogrep reset -f --all            # Clear all branches
```

## Smart Defaults

**Source-only indexing.** Full list in `ogrep/indexer.py:DEFAULT_EXCLUDES`.

Excluded categories: binaries, secrets (`.env`), docs (`*.md`), config (`*.json`, `*.toml`), build artifacts, lock files, images, fonts, media, archives, databases, logs, backups, data files.

**YAML files are indexed** (CI/CD, K8s manifests).

**Chunk size:** 60 lines, 10-line overlap. Run `ogrep tune .` to optimize.

### AST-Aware Chunking (Default)

**AST chunking is now the default** when tree-sitter is available. This splits code by semantic boundaries (functions, classes) instead of arbitrary line counts, improving search quality.

```bash
# Install AST support (if not already installed)
pip install "ogrep[ast]"        # Core languages (Python, JS, TS, Go, Rust)
pip install "ogrep[ast-all]"    # All languages (+ Ruby, Java, C, C++, C#, Bash)

# Index with AST chunking (default behavior)
ogrep index .

# Disable AST chunking (use line-based)
ogrep index . --no-ast
```

**Supported languages:** Python, JavaScript, TypeScript, TSX, Go, Rust (core); Ruby, Java, C, C++, C#, Bash (with `[ast-all]`)

**Fallback behavior:**
- Unsupported file types → line-based chunking
- Parse errors → line-based chunking
- tree-sitter not installed → line-based chunking (with JSON hint)

**JSON output includes AST status:**
```json
{
  "ast_mode": "enabled",  // or "disabled", "unavailable"
  "ast_hint": "Install AST support: pip install 'ogrep[ast]'"  // when unavailable
}
```

## Embedding Models

| Model | Alias | Dims | Use Case |
|-------|-------|------|----------|
| text-embedding-3-small | `small` | 1536 | Default (OpenAI) |
| text-embedding-3-large | `large` | 3072 | High accuracy |
| voyage-code-3 | `voyage` | 1024 | Code-optimized (Voyage AI) |
| voyage-3-lite | `voyage-lite` | 512 | Faster/cheaper (Voyage AI) |
| nomic-embed-text-v1.5 | `nomic` | 768 | Local (recommended) |
| all-MiniLM-L6-v2 | `minilm` | 384 | Local (fastest) |

**Local models:** See `LOCAL_EMBEDDINGS_GUIDE.md` for LM Studio setup.

**Smart default model selection** (based on available API keys): `OGREP_BASE_URL` → nomic, `VOYAGE_API_KEY` only → voyage-code-3, `OPENAI_API_KEY` → text-embedding-3-small.

**Voyage AI** requires `pip install "ogrep[voyage]"` and `VOYAGE_API_KEY`. Provides code-optimized embeddings (voyage-code-3) and reranking (rerank-2.5).

## Environment Variables

**API Keys (set at least one):**

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | For OpenAI models (text-embedding-3-small/large) |
| `VOYAGE_API_KEY` | For Voyage AI models (voyage-code-3, voyage-3-lite) |
| `OGREP_BASE_URL` | For local models via LM Studio (e.g., `http://localhost:1234/v1`) |

You only need **one** of these. The default model is automatically selected based on which key is available (see "Smart default model selection" above).

**Configuration:**

| Variable | Description |
|----------|-------------|
| `OGREP_MODEL` | Override default embedding model |
| `OGREP_SEARCH_MODE` | Default mode (semantic/fulltext/hybrid) |
| `OGREP_CHUNK_LINES` | Override chunk size |
| `OGREP_RERANK_MODEL` | Default rerank model (flashrank/voyage/minilm/bge-m3) |
| `OGREP_RERANK_TOPN` | Candidates to rerank (default: 50) |
| `OGREP_RERANK_LOCK` | Lock file path for parallel safety (sentence-transformers only) |
| `OGREP_RERANK_LOCK_TIMEOUT` | Lock timeout in seconds (default: 120) |
| `OGREP_VOYAGE_TIMEOUT` | Voyage API request timeout in seconds (default: 120) |
| `OGREP_VOYAGE_RETRIES` | Voyage API max retries (default: 2) |
| `OGREP_VOYAGE_CHARS_PER_TOKEN` | Token estimation ratio for Voyage batching (default: 1.0) |

Full list: grep for `OGREP_` in codebase or check `ogrep --help`.

## Development

```bash
source .venv/bin/activate
pip install -e ".[dev]"
make test      # pytest
make lint      # ruff + yamllint
make fmt       # format
make typecheck # mypy
make check     # all
```

### Key Files

| File | Purpose |
|------|---------|
| `ogrep/cli.py` | CLI dispatch |
| `ogrep/commands/` | Command implementations |
| `ogrep/models.py` | Model definitions |
| `ogrep/indexer.py` | Indexing + DEFAULT_EXCLUDES |
| `ogrep/search.py` | Query execution |
| `ogrep/db.py` | SQLite schema |
| `ogrep/embed.py` | Embedding API calls (OpenAI, Voyage, local) |
| `ogrep/rerank.py` | Reranking backends (flashrank, voyage, sentence-transformers) |
| `ogrep/ast_chunking.py` | Tree-sitter AST chunking |
| `ogrep/chunking.py` | Line-based chunking |
| `ogrep/cache.py` | Embedding cache logic |
| `ogrep/filetype.py` | File type detection + exclusion patterns |

### Adding a Command

1. Create `ogrep/commands/<name>.py` with `cmd_<name>`
2. Export from `ogrep/commands/__init__.py`
3. Add parser in `cli.py:_build_parser()`
4. Add tests in `tests/test_cli.py`
5. Add `plugins/ogrep/commands/<name>.md`

## Version Bumping

Update ALL files:

| File | Field |
|------|-------|
| `pyproject.toml` | `version` |
| `ogrep/__init__.py` | `__version__` |
| `ogrep/cli.py` | `__version__` |
| `.claude-plugin/marketplace.json` | `version` (top-level only) |
| `plugins/ogrep/.claude-plugin/plugin.json` | `version` |
| `tests/test_cli.py` | Version assertion |

**CRITICAL:** In marketplace.json, `plugins[]` array only allows `name`, `source`, `description`. Do NOT add `version`/`author`/`category` inside plugins array.

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push && git push --tags
```

## Scope Fencing

The `.ogrep/` directory is **always created in the git repository root**, not the current working directory. This means you can run `ogrep index .` from any subdirectory and the index will be stored at the repo root.

| Scope | Location |
|-------|----------|
| Default | `<git-root>/.ogrep/index.sqlite` |
| Profile | `<git-root>/.ogrep/<profile>/index.sqlite` |
| Global | `~/.cache/ogrep/<hash>/index.sqlite` |
| Explicit | `--db /path/to/db.sqlite` |

For non-git directories, `.ogrep/` is created in the indexed directory itself.

## Testing

Tests use mock OpenAI (see `conftest.py`). Integration tests:
```bash
OGREP_INTEGRATION_TESTS=1 pytest -m integration
```
