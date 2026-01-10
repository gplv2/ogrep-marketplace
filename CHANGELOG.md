# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-01-10

### Added

- **Local Embedding Models**: Run semantic search completely offline using LM Studio. No API keys required, zero cost.
  ```bash
  # Set up local server
  lms get nomic-embed-text-v1.5 -y
  lms load nomic-ai/nomic-embed-text-v1.5-GGUF -y
  lms server start

  # Index with local model
  export OGREP_BASE_URL=http://localhost:1234/v1
  ogrep index . -m nomic
  ```

- **Supported Local Models**:
  - `nomic-embed-text-v1.5` (alias: `nomic`, `local`) - Starting default: 90-line chunks
  - `bge-base-en-v1.5` (alias: `bge`) - Starting default: 30-line chunks

- **Model-Specific Chunk Size Defaults**: The CLI provides sensible starting defaults per model:
  - `nomic`: 90 lines
  - `bge`: 30 lines
  - OpenAI models: 60 lines

  These are starting points based on initial testing. **Your codebase may have different optimal settings** - use `ogrep tune` to find what works best for your repository.

- **OGREP_CHUNK_LINES Environment Variable**: Save your tuned chunk size to use it automatically:
  ```bash
  # After running: ogrep tune . -m nomic
  # If tune recommends 75 lines for your codebase:
  export OGREP_CHUNK_LINES=75
  ```

- **New API Function**: `get_optimal_chunk_lines(model)` returns the chunk size (env var > model default).

- **Comprehensive Documentation**: New `docs/LOCAL_EMBEDDINGS_GUIDE.md` with:
  - Step-by-step LM Studio installation for macOS/Linux/Windows
  - Model download and loading commands (`lms get`, `lms load`)
  - Full tuning benchmark data comparing nomic vs bge
  - Query quality analysis with real test results
  - Troubleshooting guide

### Changed

- **CLI Help**: `--chunk-lines` now shows model-specific defaults in help text
- **EmbeddingModel Dataclass**: Added `optimal_chunk_lines` field for per-model tuning

### Documentation

- Updated CLAUDE.md with local model setup, chunk tuning section, and `lms get` download instructions
- Added tuning results table showing model performance differences

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
