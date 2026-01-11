# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.5] - 2026-01-11

### ✨ New Features

#### File Type Detection with `file` Command

ogrep now uses the system `file` command for accurate MIME-type detection, catching binary files that slip through extension-based filtering:

```bash
ogrep index . --list
```

Output now shows detection results:
```
── .py (34 files, 179.6KB) ──
      101B  ogrep/__main__.py
    17.0KB  ogrep/commands/benchmark.py

── (no extension) (3 files, 45.2KB) ──
  [BINARY: application/x-sqlite3]   12.0KB  data
      25.2KB  Makefile

──────────────────────────────────────────────────
Would index: 35 files, 180.4KB
Excluded by detection: 1 files, 12.0KB
```

- Uses `file --mime-type -b` for robust detection
- Processes in batches of 500 for large repos (30K+ files)
- Falls back to null-byte detection if `file` command unavailable
- Use `--no-detect` to disable MIME detection for faster scans

#### `.ogrepignore` File Support

Create a `.ogrepignore` file in your repo root for persistent exclude patterns:

```bash
# .ogrepignore
*.sql
migrations/*
legacy/*
*.generated.ts
```

Patterns use glob syntax (like `.gitignore`). Loaded automatically on every index operation.

#### Preview Mode with `--list`

See exactly what files will be indexed before committing:

```bash
ogrep index . --list
```

Features:
- Files grouped by extension, sorted by size (biggest last)
- Binary files marked with `[BINARY: mime/type]`
- Summary of indexable vs excluded files
- **Top 10 directories by file count** — helps identify where to focus
- **Largest indexable files** — spot potential problems
- **Review suggestions** — flags files that pass MIME detection but may not be useful code

#### Review Suggestions for Non-Code Files

The `--list` output now includes a "Review suggested" section for files that:
- Have extensions like `.log`, `.old`, `.bak`, `.dump`, `.csv`
- Have filenames suggesting logs/backups (e.g., `*.log.old`, `*_backup`)
- Are large (>500KB) without code extensions

These files pass MIME detection but may distort search results. Add patterns to `.ogrepignore` to exclude them.

### 🔧 Improvements

#### Expanded Default Exclusions

New patterns added to `DEFAULT_EXCLUDES`:

| Category | New Patterns |
|----------|--------------|
| **Temp files** | `*.tmp`, `*.temp` |
| **Backups** | `*.old`, `*.bak`, `*.backup`, `*.orig`, `*.swp`, `*~` |
| **Data files** | `*.csv`, `*.tsv`, `*.sqlt`, `*.dat`, `*.xml` |
| **Database** | `*.dump` (added to existing `*.sql`, `*.sqlite`, etc.) |

#### Batched File Detection

File type detection now processes files in batches of 500 to handle large repositories (30K+ files) without hitting command-line length limits or timeouts.

### 📚 Documentation

- Updated CLAUDE.md with new features and default excludes
- Added `.ogrepignore` syntax documentation
- Documented `--list` and `--no-detect` flags

### 🧪 Testing

- 182 tests passing
- New tests for file type detection (`test_filetype.py`)
- Updated version assertion in test suite

## [0.4.3] - 2026-01-11

### 🐛 Fixes

- **CI tests now pass without API keys**: Fixed test suite failing in GitHub Actions due to missing `OPENAI_API_KEY`. The mock fixture now properly sets a fake API key so `require_embedding_config()` passes before the mock client is used

### 📚 Documentation

- Added critical warning to version bump guide about not modifying marketplace JSON structure (only version numbers)

## [0.4.2] - 2026-01-11

### 📚 Documentation

- **Developer guide**: Added version bump checklist to CLAUDE.md to ensure all 7 version files are updated consistently during releases

## [0.4.1] - 2026-01-11

### 🔧 Improvements

- **Smarter Claude Code integration**: The semantic-grep skill now activates proactively when you ask conceptual questions like "where is X handled?" or "how does Y work?" — no need to explicitly request semantic search

### 🐛 Fixes

- **Clear error when API not configured**: Commands now fail immediately with helpful guidance when neither `OPENAI_API_KEY` nor `OGREP_BASE_URL` is set, instead of silently producing misleading output like "285 files skipped"

- **Fixed PyPI installation**: Removed invalid classifier that was blocking `pip install` from source

## [0.4.0] - 2026-01-11 — Local Embeddings

**Run semantic code search completely offline. Zero API costs. Total privacy.**

### ✨ New Features

#### Run Locally with LM Studio

No more API keys required! ogrep now works with local embedding models through LM Studio's OpenAI-compatible API.

```bash
lms get all-MiniLM-L6-v2 -y
lms load all-minilm-l6-v2 -y
lms server start

export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index .   # Auto-uses minilm
```

#### Four Local Models to Choose From

| Model | Alias | Accuracy | Index Time | Best For |
|-------|-------|----------|------------|----------|
| Nomic | `nomic` | **88%** | 33.5s | Highest accuracy |
| BGE | `bge` | **88%** | 21.6s | Accuracy + speed |
| **MiniLM** | `minilm` | 84% | **5.8s** | Speed (6x faster, recommended) |
| BGE-M3 | `bge-m3` | 76% | 81.5s | Multi-lingual (100+ languages) |

All local models outperform OpenAI cloud models (48-52%) on code search tasks.

#### Model Benchmarking

Compare all models head-to-head with the new benchmark command:

```bash
ogrep benchmark . -s 10
```

Tests accuracy, speed, and optimal chunk/overlap settings across all available models. Includes warnings about time and API credit consumption for large repos.

#### Smart Tuning with Auto-Save

Different models need different chunk sizes. Now ogrep handles it automatically and remembers your settings:

```bash
ogrep tune . -m minilm --save --apply
```

The `--save` flag writes optimal settings to `.env` so you don't have to remember.

### 🔧 Improvements

- **Smart Model Default**: When `OGREP_BASE_URL` is set (local server), ogrep now defaults to `minilm` automatically—no need for `-m` flag on every command
- **Model-Specific Defaults**: Each local model now has tuned chunk size defaults based on comprehensive benchmarking (all models: 30-line chunks except BGE-M3: 60 lines)
- **OGREP_CHUNK_LINES**: New environment variable to persist your tuned chunk size across sessions
- **Timing Infrastructure**: `embed_texts()` now optionally returns elapsed time via `return_timing=True`
- **Overlap Testing**: Benchmark tests different overlap values (5, 10, 15 lines) alongside chunk sizes
- **New API Function**: `get_optimal_chunk_lines(model)` returns the chunk size (env var > model default)
- **Faster Benchmarks**: Reduced default test configurations from 20 to 9 per model

### 📚 Documentation

- Overhauled README with local model quick start and provider comparison
- New `LOCAL_EMBEDDINGS_GUIDE.md` with step-by-step LM Studio setup for macOS/Linux/Windows
- Comprehensive analysis of why local models outperform cloud models for code retrieval
- Added 6-model benchmark comparison (MiniLM, Nomic, BGE, BGE-M3, OpenAI small, OpenAI large)
- Updated CLAUDE.md with local model setup and chunk tuning section

### 🧪 Testing

- 151 tests passing
- New test files: `test_benchmark.py`, `test_embed.py`, `test_models.py`, `test_search.py`, `test_query_command.py`

## [0.3.4] - 2026-01-10

### Added

- **Refresh Command**: New `/ogrep:refresh` slash command for manually refreshing the index before queries. Runs incremental reindex on changed files.

## [0.3.3] - 2026-01-10

### Added

- **Query Refresh Flag**: New `--refresh` (`-r`) flag for the query command that automatically checks for changed files and reindexes before searching:
  ```bash
  ogrep query "where is auth handled" --refresh
  ```
  This ensures AI tools always get accurate results reflecting the current codebase state.

- **Stale File Detection**: Query command can now detect files that have been modified or deleted since last indexing by comparing mtime/size.

- **Claude Code Hook Documentation**: Added documentation for configuring Claude Code hooks to auto-reindex after file edits as an alternative to `--refresh`.

### Changed

- **Skill Updated**: The semantic-grep skill now uses `--refresh` by default to prevent stale results.
- **Plugin Query Command**: Updated to use `--refresh` flag.

### Documentation

- New "AI Tool Integration" section in CLAUDE.md explaining `--refresh` flag and hook configuration.
- Added 2 new tests for stale file detection (42 tests total).

## [0.3.2] - 2026-01-10

### Fixed

- **Test Cleanup**: Removed unused imports and variables in embedding reuse tests

## [0.3.1] - 2026-01-10

### Added

- **Expanded Default Exclusions**: More comprehensive filtering for source-only indexing:
  - **Directories**: `venv/`, `.githooks/`, `storage/` (Laravel), `.mypy_cache/`, `.tox/`, `.pytest_cache/`, `.ruff_cache/`
  - **Git metadata**: `.gitignore`, `.gitattributes`, `.gitmodules`, `.gitkeep`
  - **Images**: `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.webp`, `*.ico`, `*.bmp`, `*.tiff`, `*.psd`
  - **Fonts**: `*.woff`, `*.woff2`, `*.ttf`, `*.otf`, `*.eot`
  - **Media**: `*.mp3`, `*.mp4`, `*.wav`, `*.avi`, `*.mov`, `*.webm`
  - **Archives**: `*.zip`, `*.tar`, `*.gz`, `*.rar`, `*.7z`
  - **Databases**: `*.sqlite`, `*.sqlite3`, `*.db`
  - **Logs**: `*.log`, `logs/*`
  - **Python packages**: `*.dist-info/*`, `*.pth`, `py.typed`
  - **Config**: `.editorconfig`, `.phpunit.result.cache`

### Fixed

- **Non-Interactive Reset**: `ogrep reset` now requires `-f` flag when running non-interactively (e.g., from Claude Code) instead of crashing with EOFError

## [0.3.0] - 2026-01-10

### Added

- **Smart Embedding Reuse**: Save ~80% on API tokens when re-indexing! When files change, ogrep now reuses embeddings for unchanged chunks instead of re-embedding everything.
  ```
  Files: 3 indexed, 42 skipped
  Chunks: 12 total (9 reused, ~900 tokens saved)
  ```

- **Auto-Tuning**: New `ogrep tune` command finds the optimal chunk size for your codebase:
  - Tests chunk sizes 30, 45, 60, 90, 120 lines
  - Samples real function/class definitions as test patterns
  - Reports accuracy scores and recommends best setting
  - `ogrep tune . --apply` to auto-reindex with optimal settings

- **Smart Source-Only Defaults**: ogrep now focuses on source code by default:
  - Excludes: docs (`*.md`), config (`*.json`, `*.yaml`), build outputs, lock files
  - Excludes secrets: `.env`, `credentials.*`, `secrets.*`
  - Skips: `.git/`, `node_modules/`, `.venv/`, `__pycache__/`

- **File Filtering Flags**:
  - `-e/--exclude PATTERN`: Add patterns to exclude (e.g., `-e 'test_*'`)
  - `-i/--include PATTERN`: Override default excludes (e.g., `-i '*.md'` to index markdown)

- **Indexing Statistics**: See what happened during indexing:
  - Files indexed vs skipped
  - Chunks embedded vs reused
  - Estimated tokens saved

### Fixed

- **Model Mismatch Error**: Clear error message when querying with wrong model:
  ```
  Dimension mismatch: query uses 3072D (large) but index was built with 1536D (small).
  Use -m small or reindex with -m large.
  ```

### Technical

- 40 tests passing (up from 27)
- 13 new tests for embedding reuse feature
- Optimal default chunk size: 60 lines (tested for best relevance)

## [0.2.0] - 2026-01-10

### Added

- **Configurable Embedding Models**: Choose from multiple OpenAI embedding models:
  - `text-embedding-3-small` - Fast and affordable (default, $0.02/M tokens)
  - `text-embedding-3-large` - High accuracy for complex searches ($0.13/M tokens)
  - `text-embedding-ada-002` - Legacy compatibility ($0.10/M tokens)

- **Model Selection Options**:
  - CLI flag: `ogrep index . -m large`
  - Environment variable: `export OGREP_MODEL=large`
  - Model aliases: `small`, `large`, `ada`

- **New `ogrep models` Command**: View available embedding models with pricing and use cases

- **Short CLI Flags**:
  - `-m` for `--model`
  - `-d` for `--dimensions`
  - `-n` for `--top` (query results)
  - `-f` for `--force`

### Changed

- Restructured CLI into modular `ogrep/commands/` package
- Added comprehensive docstrings to all public modules
- Public Python API exports for library usage

### Technical

- 27 tests passing (up from 25)
- CLI complexity reduced from 38 to 11

## [0.1.0] - 2026-01-10

### Added

- **Semantic Code Search**: Search your codebase by meaning, not just keywords. Uses OpenAI embeddings with local SQLite storage for fast, private searches.

- **Full CLI Suite**: Complete command-line interface with `index`, `query`, `reset`, `reindex`, `clean`, and `status` commands.

- **Multi-Repo Scope Management**: Prevent cross-repo index pollution with flexible scope options:
  - `--db PATH` for custom database location
  - `--profile NAME` for named profiles
  - `--global-cache` for centralized caching
  - `--repo-root PATH` for explicit repository boundaries

- **Claude Code Integration**: Install directly from the Claude Code marketplace:
  ```
  /plugin marketplace add gplv2/ogrep-marketplace
  /plugin install ogrep@ogrep-marketplace
  ```

- Comprehensive test suite with 25 tests covering CLI, database, chunking, and end-to-end scenarios

- GitHub Actions CI workflow with Python 3.10, 3.11, 3.12 matrix testing

- Pre-commit hooks for code quality (ruff, yamllint)

- Developer documentation (CLAUDE.md, QUICKSTART.md)
