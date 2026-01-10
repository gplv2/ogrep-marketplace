# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
