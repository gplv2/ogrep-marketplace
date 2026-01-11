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
│   │   ├── tune.py           # Tune command (auto-tuning)
│   │   └── benchmark.py      # Benchmark command (model comparison)
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
| `ogrep query "text" -n 10 -r` | Semantic search (with refresh) |
| `ogrep status` | Show index stats |
| `ogrep reset -f` | Delete index |
| `ogrep reindex .` | Rebuild index |
| `ogrep clean --vacuum` | Remove stale entries |
| `ogrep models` | List available models |
| `ogrep tune .` | Auto-tune chunk size |
| `ogrep benchmark .` | Compare all models |

## AI Tool Integration (IMPORTANT)

### The --refresh Flag

**Always use `--refresh` (or `-r`) when querying from AI tools:**

```bash
ogrep query "where is auth handled" --refresh
```

The `--refresh` flag:
1. Checks all indexed files for changes (mtime/size comparison)
2. Runs incremental reindex on changed files (fast, reuses embeddings)
3. Then executes the query against fresh data

**Why this matters**: Without `--refresh`, queries may return stale results
based on outdated embeddings. This is especially critical in AI tool contexts
where files are being edited between queries.

### Claude Code Hooks (Alternative)

Instead of using `--refresh` on every query, you can configure Claude Code
to automatically reindex after file edits using hooks.

#### Hook Configuration

Create or edit `.claude/settings.json` in your project root:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "ogrep index . 2>/dev/null || true"
      }
    ]
  }
}
```

#### Hook File Locations

| Location | Scope | Path |
|----------|-------|------|
| **Project** | This repo only | `<repo>/.claude/settings.json` |
| **User** | All repos | `~/.claude/settings.json` |

#### Example: Full Hook Configuration

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "ogrep index . 2>/dev/null || true"
      }
    ]
  }
}
```

**Matcher options:**
- `"Edit|Write"` - Trigger on file edits and writes
- `"Edit"` - Only on Edit tool
- `".*"` - All tool uses (not recommended)

### When to Use Each Approach

| Approach | Best For | Trade-offs |
|----------|----------|------------|
| `--refresh` flag | General use, any environment | Small latency on each query |
| Claude Code hooks | Heavy editing sessions | Requires Claude Code, config setup |
| Both | Maximum reliability | Redundant but safe |

**Recommendation**: The semantic-grep skill uses `--refresh` by default.
Add hooks as an optimization if query latency becomes noticeable during
heavy editing sessions.

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
| `OPENAI_API_KEY` | Required for OpenAI models | - |
| `OGREP_MODEL` | Default embedding model | Smart default* |
| `OGREP_DIMENSIONS` | Default dimensions | Model default |
| `OGREP_CHUNK_LINES` | Chunk size from tuning (overrides model default) | Model-specific |
| `OGREP_BASE_URL` | Local server URL (e.g., LM Studio) | - |
| `OGREP_INTEGRATION_TESTS` | Enable real API tests | - |

**Smart Model Default:**
- If `OGREP_BASE_URL` is set → `minilm` (local model, best accuracy)
- Otherwise → `text-embedding-3-small` (OpenAI)

## Embedding Models

### OpenAI Models (Cloud)

| Model | Alias | Dimensions | Use Case |
|-------|-------|------------|----------|
| text-embedding-3-small | `small` | 1536 | Default, cost-effective |
| text-embedding-3-large | `large` | 3072 | High accuracy |
| text-embedding-ada-002 | `ada` | 1536 | Legacy |

### Local Models (via LM Studio)

| Model | Alias | Dimensions | Use Case |
|-------|-------|------------|----------|
| bge-base-en-v1.5 | `bge` | 768 | Local/offline, privacy |
| nomic-embed-text-v1.5 | `nomic`, `local` | 768 | Local/offline, privacy |

**Important:** Query model must match index model.

## Local Embedding Models

Use local embedding models for offline operation, privacy, or cost-free usage.

### Prerequisites

#### Step 1: Install LM Studio

**System Requirements:**
- 16GB RAM minimum (for embedding models)
- macOS 13.6+, Windows 10+, or Ubuntu 22.04+

Download LM Studio from [lmstudio.ai](https://lmstudio.ai/):

**macOS:**
1. Download the DMG from [lmstudio.ai](https://lmstudio.ai/)
2. Open the DMG and drag LM Studio to Applications
3. **Launch LM Studio once** - this creates `~/.lmstudio/` directory

**Linux (Ubuntu/Debian):**
1. Download the AppImage from [lmstudio.ai](https://lmstudio.ai/)
2. Make executable: `chmod +x LM-Studio-*.AppImage`
3. **Run it once**: `./LM-Studio-*.AppImage` - this creates `~/.lmstudio/` directory
4. Close LM Studio after it finishes initializing

**Windows:**
1. Download the installer from [lmstudio.ai](https://lmstudio.ai/)
2. Run the EXE installer
3. **Launch LM Studio once** - this creates the `.lmstudio` directory

> **Important:** You must launch LM Studio at least once before proceeding.
> The CLI is only available after LM Studio creates the `~/.lmstudio/` directory.

#### Step 2: Add CLI to PATH

After LM Studio has been launched once, add the `lms` CLI to your PATH:

**macOS/Linux:**
```bash
~/.lmstudio/bin/lms bootstrap
lms --version  # Verify: should show version number
```

**Windows (PowerShell):**
```powershell
& "$env:USERPROFILE\.lmstudio\bin\lms.exe" bootstrap
lms --version
```

**Troubleshooting:** If you get "command not found" or "directory not found":
- Ensure LM Studio was launched at least once
- Check that `~/.lmstudio/bin/lms` exists: `ls ~/.lmstudio/bin/`
- If using a custom install location, check `~/.lmstudio-home-pointer`:
  ```bash
  cat ~/.lmstudio-home-pointer  # Shows actual LM Studio home
  # Then use that path, e.g.:
  ~/.cache/lm-studio/bin/lms bootstrap
  ```
- If missing, launch LM Studio again and wait for it to fully initialize

### Setup

1. **Download an embedding model:**
   ```bash
   # Download nomic (recommended - good balance of speed and quality)
   lms get nomic-embed-text-v1.5 -y

   # Or download BGE (higher quality quantization)
   lms get bge-base-en-v1.5 -y

   # List downloaded models
   lms ls
   ```

2. **Load the model into memory:**
   ```bash
   # Load nomic
   lms load nomic-ai/nomic-embed-text-v1.5-GGUF -y

   # Or load BGE
   lms load bge-base-en-v1.5 -y
   ```

3. **Start the server:**
   ```bash
   lms server start --port 1234
   lms server status  # Verify: "Server: ON (port: 1234)"
   ```

4. **Configure ogrep:**
   ```bash
   export OGREP_BASE_URL=http://localhost:1234/v1
   ```

### Usage

```bash
# Index with local model
ogrep index . -m nomic

# Query with local model
ogrep query "where is auth handled" -m nomic -r

# Check status
ogrep status
```

### Using .env File

```bash
# .env
OGREP_BASE_URL=http://localhost:1234/v1
OGREP_MODEL=nomic-embed-text-v1.5
```

### Chunk Size Tuning

**Critical:** Different models require different chunk sizes for optimal results.

| Model | Optimal Chunk Size | Notes |
|-------|-------------------|-------|
| nomic-embed-text-v1.5 | 90 lines | Better with larger context |
| bge-base-en-v1.5 | 30 lines | Fails completely at 90+ lines |

Always tune when using a new model:

```bash
# Find optimal chunk size for your model and codebase
ogrep tune . -m nomic -s 10

# Apply the recommended setting
ogrep reindex . -m nomic --chunk-lines 90
```

### Dimension Mismatch

OpenAI models use 1536D or 3072D, local models use 768D. You cannot mix models:

```
Dimension mismatch: query uses 768D (nomic) but index was built with 1536D (small).
Use -m small or reindex with -m nomic.
```

### Auto-Start Server on Boot

Configure LM Studio settings to start the server on login without GUI.

### Detailed Tuning Guide

For comprehensive benchmarks, model comparisons, and troubleshooting, see:
[LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md)

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
