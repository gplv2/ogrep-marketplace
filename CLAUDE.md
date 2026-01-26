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

**JSON output is default.** Use `--no-json` for human-readable.

## AI Tool Integration

### Auto-Refresh Behavior

Queries automatically check for file changes and reindex stale files before searching. For heavy editing sessions, you can force a full refresh:

```bash
ogrep query "where is auth handled" --refresh
```

### Search Modes (`--mode` / `-M`)

| Mode | Best For |
|------|----------|
| `semantic` | Conceptual: "where is authentication handled" |
| `fulltext` | Exact: "def validate_token" |
| `hybrid` | Mixed/unsure (default) |

### Chunk Navigation

After query finds something, expand context:
```bash
ogrep chunk "src/auth.py:2" --context 1
```

### Reranking

Three backend options with multiple models:

| Model | Backend | Size | Context | Install |
|-------|---------|------|---------|---------|
| `flashrank` (default) | ONNX | ~4MB | 512 | `[rerank-light]` |
| `flashrank:mini` | ONNX | ~50MB | 512 | `[rerank-light]` |
| `voyage` | Voyage AI API | - | 32K | `[voyage]` |
| `voyage:lite` | Voyage AI API | - | 32K | `[voyage]` |
| `minilm` | sentence-transformers | ~90MB | 512 | `[rerank]` |
| `bge-m3` | sentence-transformers | ~300MB | 8K | `[rerank]` |

**FlashRank models are parallel-safe** (no locking needed). **Voyage models** use REST API (code-optimized, needs VOYAGE_API_KEY). Sentence-transformers models use file-based locking to prevent OOM.

```bash
ogrep query "auth" --rerank                       # Default (flashrank)
ogrep query "auth" --rerank-model flashrank:mini  # Better quality ONNX (50MB)
ogrep query "auth" --rerank-model voyage          # Voyage AI (code-optimized, 32K)
ogrep query "auth" --rerank-model voyage:lite     # Voyage AI (faster, cheaper)
ogrep query "auth" --rerank-model minilm          # Smaller PyTorch (90MB)
ogrep query "auth" --rerank-model bge-m3          # Heavy PyTorch (GPU only)
ogrep query "auth" --rerank-top 30                # Rerank top 30 candidates
```

Install backends:
```bash
pip install "ogrep[rerank-light]"  # Lightweight (FlashRank + ONNX, parallel-safe) - RECOMMENDED
pip install "ogrep[voyage]"        # Voyage AI (code-optimized embeddings + reranking)
pip install "ogrep[rerank]"        # Full-featured (sentence-transformers + PyTorch)
pip install "ogrep[rerank-all]"    # All backends
```

Check hardware and available backends: `ogrep device`.

**Note:** `--rerank-top` must be >= `-n`. Example: `-n 20 --rerank-top 15` is invalid.

**Parallel Safety:** Sentence-transformers models use file-based locking. On lock timeout (default: 120s), returns unreranked results with a warning. Configure via `OGREP_RERANK_LOCK` (path) and `OGREP_RERANK_LOCK_TIMEOUT` (seconds). **FlashRank models don't need locking** - they're safe for parallel use.

### When to Use Reranking (Benchmark Results)

**Key finding from quality benchmarks (MRR = Mean Reciprocal Rank):**

| Embedding | Without Rerank | With flashrank | Recommendation |
|-----------|----------------|----------------|----------------|
| OpenAI | **0.700** | 0.550 (-21%) | ❌ Don't rerank |
| Nomic (local) | 0.545 | **0.633** (+16%) | ✅ Use reranking |

**The rule:** Reranking **helps weak embeddings** but **hurts strong embeddings**.

- **OpenAI embeddings:** Already well-calibrated. Reranking adds noise → disable it.
- **Local embeddings (Nomic):** Less precise. Reranking compensates → use flashrank.

```bash
# OpenAI (best quality) - NO reranking
ogrep query "where is auth"

# Nomic (local/free) - WITH reranking
ogrep query "where is auth" --rerank
```

**Reranker comparison:**

| Model | MRR (Nomic) | Speed | Verdict |
|-------|-------------|-------|---------|
| flashrank | **0.633** | ~200ms | ✅ Default - best balance |
| minilm | 0.568 | ~2s | ⚠️ Optional |
| bge-m3 | 0.516 | ~30s | ❌ Too slow on CPU |

Full benchmark: `test-reports/BENCHMARK-REPORT-2026-01-16.md`

### Path Filtering (`--glob` / `--exclude`)

Filter results to specific file patterns:

```bash
ogrep query "auth" --glob "*.py"            # Only Python files
ogrep query "auth" -g "*.py" -g "*.php"     # Multiple patterns
ogrep query "auth" --exclude "tests/*"      # Exclude tests
ogrep query "auth" -g "**/*.py" -x "vendor/*"  # Combine include/exclude
```

Supports `**` for recursive matching. JSON output includes filter stats.

### Summary Mode (`--summarize`)

Get file-level aggregation without full chunk text (token-efficient):

```bash
ogrep query "authentication" --summarize
ogrep query "auth" --summarize --glob "*.py"
```

Output shows:
- Files matched with chunk counts
- Best score and score range per file
- Line ranges covered
- Recommendation to use `ogrep chunk` for expansion

~85% token savings vs full output.

### Confidence Scoring

Results include hybrid confidence combining relative position and absolute quality:

```json
"confidence": {
  "level": "medium",
  "relative_pct": 95.2,
  "absolute_quality": "weak",
  "signal": "top_result_weak_absolute"
}
```

| Field | Meaning |
|-------|---------|
| `level` | Overall: high/medium/low/very_low |
| `relative_pct` | Score as % of top result |
| `absolute_quality` | strong/expected_range/weak/very_weak |
| `signal` | Human-readable explanation |

**Key insight:** Low absolute scores (e.g., 0.03) can still be "medium" confidence if they're the best available match. The `signal` field explains why.

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

**Smart default model selection** (based on available API keys):

| Environment | Default Model |
|-------------|---------------|
| `OGREP_BASE_URL` set | `nomic-embed-text-v1.5` (local) |
| Only `VOYAGE_API_KEY` | `voyage-code-3` (code-optimized) |
| Only `OPENAI_API_KEY` | `text-embedding-3-small` |
| Both API keys | `text-embedding-3-small` (OpenAI) |

This means you only need to set the API key for the service you want to use - ogrep will automatically select the right model.

## Voyage AI Backend

Voyage AI provides **code-optimized** embeddings and reranking. Particularly good for code search.

**Setup:**
```bash
pip install "ogrep[voyage]"
export VOYAGE_API_KEY=pa-...  # Get from https://dash.voyageai.com/
```

**Embeddings:**
```bash
ogrep index . -m voyage-code-3  # Code-optimized (1024D, 32K context)
ogrep index . -m voyage-3-lite  # Faster/cheaper (512D)
```

**Reranking:**
```bash
ogrep query "auth" --rerank --rerank-model voyage       # rerank-2.5 (instruction-following)
ogrep query "auth" --rerank --rerank-model voyage:lite  # rerank-2.5-lite (faster)
```

**Full Voyage stack:**
```bash
export VOYAGE_API_KEY=pa-...
ogrep index . -m voyage-code-3
ogrep query "where is auth" --rerank --rerank-model voyage
```

| Component | Model | Context | Notes |
|-----------|-------|---------|-------|
| Embeddings | voyage-code-3 | 32K | Code-optimized, 1024D |
| Embeddings | voyage-3-lite | 32K | Faster, 512D |
| Reranking | rerank-2.5 | 32K | Instruction-following |
| Reranking | rerank-2.5-lite | 32K | Faster/cheaper |

## Recommended Configurations

Based on quality benchmarks (10 ground-truth queries, MRR metric):

### Maximum Quality (Cloud)
```bash
export OPENAI_API_KEY=...
ogrep index .
ogrep query "your search"  # NO --rerank flag
```
- **MRR: 0.700** (best achievable)
- Fast indexing: ~30s for 285 files
- Cost: ~$0.02 per index

### Privacy/Offline (Local)
```bash
export OGREP_BASE_URL=http://localhost:1234/v1
export OGREP_MODEL=nomic
ogrep index .
ogrep query "your search" --rerank  # flashrank default
```
- **MRR: 0.633** (-9.5% vs OpenAI)
- Zero cost, fully offline
- Slower indexing: ~17 min for 285 files

### Decision Matrix

| Requirement | Configuration |
|-------------|---------------|
| Maximum accuracy | OpenAI, no reranking |
| Privacy/compliance | Nomic + flashrank |
| Offline capability | Nomic + flashrank |
| Minimum cost | Nomic + flashrank |
| Fastest indexing | OpenAI |
| Fastest queries | Any, no reranking |

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
make test    # pytest
make lint    # ruff + yamllint
make fmt     # format
make check   # all
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
