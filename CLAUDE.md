# CLAUDE.md - ogrep Developer Guide

## Overview

**ogrep** is a local semantic grep tool: SQLite index + OpenAI/local embeddings + FTS5 hybrid search + branch-aware indexing.

## CLI Quick Reference

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index directory (source files only) |
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
| `ogrep tune .` | Auto-tune chunk size |

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

```bash
ogrep query "auth" --rerank              # Rerank top 50
ogrep query "auth" --rerank-top 30       # Rerank top 30
```
Requires `pip install "ogrep[rerank]"`. Check hardware: `ogrep device`.

**Note:** `--rerank-top` must be >= `-n`. Example: `-n 20 --rerank-top 15` is invalid.

**Parallel Safety:** The ~300MB cross-encoder model uses file-based locking to prevent OOM when multiple processes run `--rerank` simultaneously. On lock timeout (default: 120s), returns unreranked results with a warning. Configure via `OGREP_RERANK_LOCK` (path) and `OGREP_RERANK_LOCK_TIMEOUT` (seconds).

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

## Embedding Models

| Model | Alias | Dims | Use Case |
|-------|-------|------|----------|
| text-embedding-3-small | `small` | 1536 | Default (OpenAI) |
| text-embedding-3-large | `large` | 3072 | High accuracy |
| nomic-embed-text-v1.5 | `nomic` | 768 | Local (recommended) |
| all-MiniLM-L6-v2 | `minilm` | 384 | Local (fastest) |

**Local models:** See `LOCAL_EMBEDDINGS_GUIDE.md` for LM Studio setup.

**Smart default:** If `OGREP_BASE_URL` set → `nomic`, else → `small`.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required for OpenAI models |
| `OGREP_MODEL` | Default model |
| `OGREP_BASE_URL` | Local server URL |
| `OGREP_SEARCH_MODE` | Default mode (semantic/fulltext/hybrid) |
| `OGREP_CHUNK_LINES` | Override chunk size |
| `OGREP_RERANK_LOCK` | Lock file path for parallel safety |
| `OGREP_RERANK_LOCK_TIMEOUT` | Lock timeout in seconds (default: 120) |

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

- Default: `.ogrep/index.sqlite` in repo root
- Profile: `.ogrep/<profile>/index.sqlite`
- Global: `~/.cache/ogrep/<hash>/index.sqlite`
- Explicit: `--db /path/to/db.sqlite`

## Testing

Tests use mock OpenAI (see `conftest.py`). Integration tests:
```bash
OGREP_INTEGRATION_TESTS=1 pytest -m integration
```
