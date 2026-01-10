# CLAUDE.md - Developer Guide for Claude Code

This file provides guidance for Claude Code when working in this repository.

## Repository Overview

**ogrep** is a local semantic grep tool with:
- SQLite-based local index (no external vector DB)
- OpenAI embeddings for semantic search (configurable model)
- Smart defaults for source-only indexing
- Auto-tuning for optimal chunk size
- Claude Code plugin/skill integration
- Multi-repo scope fencing

## Directory Structure

```
ogrep-marketplace/
├── .claude-plugin/           # Marketplace config
│   └── marketplace.json
├── ogrep/                    # Python package
│   ├── __init__.py           # Public API exports
│   ├── cli.py                # CLI argument parsing
│   ├── commands/             # CLI command implementations
│   │   ├── __init__.py
│   │   ├── _common.py        # Shared utilities (scope resolution)
│   │   ├── index.py          # Index command
│   │   ├── query.py          # Query command
│   │   ├── reset.py          # Reset command
│   │   ├── reindex.py        # Reindex command
│   │   ├── clean.py          # Clean command
│   │   ├── status.py         # Status command
│   │   ├── models.py         # Models command
│   │   └── tune.py           # Tune command (auto-tuning)
│   ├── models.py             # Embedding model definitions
│   ├── db.py                 # SQLite schema/connection
│   ├── indexer.py            # File indexing logic + DEFAULT_EXCLUDES
│   ├── search.py             # Query/search logic
│   ├── embed.py              # OpenAI embeddings
│   ├── chunking.py           # Text chunking
│   └── mcp/                  # MCP server (optional)
├── plugins/ogrep/            # Claude Code plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── commands/             # Slash commands
│   └── skills/               # Skills
├── tests/                    # Test suite
├── pyproject.toml            # Package config
├── .env.example              # Environment template
├── .pre-commit-config.yaml   # Pre-commit hooks
├── .yamllint.yaml            # YAML linting config
├── Makefile                  # Development commands
└── activate.sh               # Venv activation helper
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index a directory (source files only) |
| `ogrep query "text" -n 10` | Semantic search |
| `ogrep status` | Show index stats |
| `ogrep reset -f` | Delete index |
| `ogrep reindex .` | Rebuild index |
| `ogrep clean --vacuum` | Remove stale entries |
| `ogrep models` | List available models |
| `ogrep tune .` | Auto-tune chunk size |

## Smart Defaults

### Source-Only Indexing

Defined in `ogrep/indexer.py` as `DEFAULT_EXCLUDES`:

| Category | Patterns |
|----------|----------|
| **Binary** | `*.pyc`, `*.so`, `*.dll`, `*.exe`, `*.whl` |
| **Secrets** | `.env`, `.env.*`, `secrets.*`, `credentials.*` |
| **Docs** | `*.md`, `*.txt`, `*.rst`, `docs/*` |
| **Config** | `*.json`, `*.yaml`, `*.yml`, `*.toml`, `*.ini`, `.editorconfig` |
| **Build** | `dist/*`, `build/*`, `vendor/*`, `target/*` |
| **Lock files** | `*.lock`, `package-lock.json`, `yarn.lock`, `poetry.lock` |
| **Git metadata** | `.gitignore`, `.gitattributes`, `.gitmodules`, `.gitkeep` |
| **Images** | `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.webp`, `*.ico`, `*.bmp`, `*.tiff`, `*.psd` |
| **Fonts** | `*.woff`, `*.woff2`, `*.ttf`, `*.otf`, `*.eot` |
| **Media** | `*.mp3`, `*.mp4`, `*.wav`, `*.avi`, `*.mov`, `*.webm` |
| **Archives** | `*.zip`, `*.tar`, `*.gz`, `*.rar`, `*.7z` |
| **Databases** | `*.sqlite`, `*.sqlite3`, `*.db` |
| **Logs** | `*.log`, `logs/*` |
| **Python packages** | `*.dist-info/*`, `*.egg-info/*`, `*.pth`, `py.typed` |

**Skipped directories** (in `DEFAULT_SKIP_DIRS`):
- `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.ogrep`
- `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.tox`
- `.githooks`, `storage`

### Chunk Size Optimization

Default: **60 lines** with 10-line overlap.

Tested results:

| Chunk Size | Accuracy | Notes |
|------------|----------|-------|
| 30 lines | 0.64 | Too granular |
| 45 lines | 0.88 | Good |
| **60 lines** | **0.92** | **Best (default)** |
| 90 lines | 0.92 | Equivalent |
| 120 lines | 0.92 | Larger context |

### Smart Embedding Reuse

Implemented in `ogrep/indexer.py` - minimizes API token usage:

1. **File unchanged**: Completely skipped (mtime, size, sha256 match)
2. **File modified**: Cache existing chunk embeddings by `text_sha256` before delete
3. **Re-chunk**: Compute new chunk hashes
4. **Reuse**: Match new hashes against cached embeddings
5. **Embed**: Only call API for truly new chunks

**Key code path:**
```python
# Cache existing embeddings before deletion
existing_embeddings = {r[0]: (r[1], r[2]) for r in
    con.execute("SELECT text_sha256, embedding, dim FROM chunks WHERE file_id=?")}

# After re-chunking, check each chunk's hash
if tsha in existing_embeddings:
    reusable_indices.append((i, existing_embeddings[tsha]))
else:
    chunks_to_embed.append((i, text))
```

**`IndexStats` dataclass** tracks: `files_scanned`, `files_indexed`, `files_skipped`, `chunks_total`, `chunks_reused`, `chunks_embedded`, `tokens_saved_estimate`.

## File Filtering Flags

| Flag | Description |
|------|-------------|
| `-e`, `--exclude PATTERN` | Add patterns to exclude |
| `-i`, `--include PATTERN` | Override default excludes |

Examples:
```bash
ogrep index . -e 'test_*'      # Exclude test files
ogrep index . -i '*.md'        # Include markdown (normally excluded)
```

## Auto-Tuning

The `tune` command tests different chunk sizes:

```bash
ogrep tune .           # Test and recommend
ogrep tune . --apply   # Test and reindex with optimal settings
ogrep tune . -s 10     # Use 10 test samples
```

**How it works:**
1. Scans for significant patterns (function/class definitions)
2. Creates semantic queries ("where is function X defined")
3. Tests chunk sizes: 30, 45, 60, 90, 120
4. Measures if correct file+line appears in top 5 results
5. Reports accuracy and recommends optimal chunk size

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Required. OpenAI API key | - |
| `OGREP_MODEL` | Default embedding model | `text-embedding-3-small` |
| `OGREP_DIMENSIONS` | Default dimensions | Model default |
| `OGREP_INTEGRATION_TESTS` | Enable real API tests | - |

## Embedding Models

| Model | Alias | Dimensions | Use Case |
|-------|-------|------------|----------|
| text-embedding-3-small | `small` | 1536 | Default, cost-effective |
| text-embedding-3-large | `large` | 3072 | High accuracy |
| text-embedding-ada-002 | `ada` | 1536 | Legacy |

**Important:** Query model must match index model.

## Development Workflow

### Setup

```bash
source .venv/bin/activate
pip install -e ".[dev]"
```

### Testing

```bash
make test        # Run pytest
make lint        # Run ruff + yamllint
make fmt         # Format code
make check       # All checks
```

### Key Files to Know

| File | Purpose |
|------|---------|
| `ogrep/cli.py` | CLI argument parsing and dispatch |
| `ogrep/commands/` | Individual command implementations |
| `ogrep/models.py` | Embedding model definitions and resolution |
| `ogrep/indexer.py` | File walking, filtering, indexing logic |
| `ogrep/search.py` | Query execution and scoring |
| `ogrep/db.py` | SQLite schema and connection |
| `tests/conftest.py` | Pytest fixtures with OpenAI mock |

## Common Tasks

### Adding a new CLI command

1. Create `ogrep/commands/<name>.py` with `cmd_<name>` function
2. Export from `ogrep/commands/__init__.py`
3. Add parser in `cli.py` `_build_parser()` function
4. Add tests in `tests/test_cli.py`
5. Add command file in `plugins/ogrep/commands/<name>.md`

### Modifying default excludes

1. Edit `DEFAULT_EXCLUDES` tuple in `ogrep/indexer.py`
2. Run tests to ensure nothing breaks
3. Update documentation

### Adding a new embedding model

1. Add entry to `MODELS` dict in `models.py`
2. Optionally add alias to `MODEL_ALIASES`
3. Update documentation

### Adding a new skill

1. Create `plugins/ogrep/skills/<name>/SKILL.md`
2. Define frontmatter with `name`, `description`, `allowed-tools`
3. Document skill behavior in markdown body

## Debugging Tips

```bash
# Check index status
ogrep status

# Reset and reindex
ogrep reindex .

# View database directly
sqlite3 .ogrep/index.sqlite

# Check for stale files
ogrep clean --vacuum

# List models
ogrep models

# Test chunk sizes
ogrep tune . -s 5
```

## Plugin Structure

The Claude Code plugin is at `plugins/ogrep/`:

```
plugins/ogrep/
├── .claude-plugin/plugin.json   # Plugin manifest
├── commands/                     # Slash commands
│   ├── index.md
│   ├── query.md
│   ├── reset.md
│   ├── reindex.md
│   ├── clean.md
│   └── status.md
└── skills/semantic-grep/        # Skills
    └── SKILL.md
```

## Scope Fencing

Prevents cross-repo pollution:

1. **Default**: `.ogrep/index.sqlite` in repo root
2. **Profile**: `.ogrep/<profile>/index.sqlite`
3. **Global cache**: `~/.cache/ogrep/<hash>/index.sqlite`
4. **Explicit**: `--db /path/to/db.sqlite`

## Testing Notes

- Tests use a mock OpenAI client by default (see `conftest.py`)
- Real API tests are marked with `@pytest.mark.integration`
- Run integration tests with: `OGREP_INTEGRATION_TESTS=1 pytest -m integration`

### Test Files

| File | Coverage |
|------|----------|
| `tests/test_chunking.py` | Text chunking logic |
| `tests/test_cli.py` | CLI help and argument parsing |
| `tests/test_db.py` | Database schema and connections |
| `tests/test_roundtrip.py` | End-to-end index/query flow |
| `tests/test_embedding_reuse.py` | Smart embedding reuse (13 tests) |

### Key Embedding Reuse Tests

- `test_embedding_reuse_on_small_edit`: Verifies unchanged chunks reuse embeddings
- `test_embedding_reuse_append_only`: Tests common append-only edit pattern
- `test_embedding_preserved_in_db`: Confirms reused embeddings are byte-identical
- `test_tokens_saved_estimate`: Validates savings calculation
