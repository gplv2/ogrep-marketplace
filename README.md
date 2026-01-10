# ogrep

Local semantic grep powered by:
- **SQLite index** (`.ogrep/index.sqlite` by default)
- **OpenAI embeddings** (configurable model)

Search your codebase by meaning, not just keywords.

## Installation

### Option A: pip / pipx (Recommended for CLI users)

```bash
# Install with pipx (isolated environment)
pipx install ogrep

# Or with pip
pip install ogrep

# Set your OpenAI API key
export OPENAI_API_KEY="sk-..."
```

### Option B: Claude Code Marketplace + Plugin

```bash
# Add the marketplace
/plugin marketplace add gplv2/ogrep-marketplace

# Install the plugin
/plugin install ogrep@ogrep-marketplace
```

### Optional Extras

```bash
pip install "ogrep[speed]"   # Faster scoring with numpy
pip install "ogrep[mcp]"     # MCP server support
```

## Quick Start

```bash
# Index the current directory (source files only by default)
ogrep index .

# Semantic search
ogrep query "where is authentication handled?" -n 15

# Check index status
ogrep status

# Auto-tune chunk size for your codebase
ogrep tune .
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index current directory |
| `ogrep query "text" -n 10` | Semantic search |
| `ogrep status` | Show index statistics |
| `ogrep reset -f` | Delete index |
| `ogrep reindex .` | Rebuild from scratch |
| `ogrep clean --vacuum` | Remove stale entries |
| `ogrep models` | List available embedding models |
| `ogrep tune .` | Auto-tune chunk size |

## Smart Defaults

ogrep is optimized for **source code search** out of the box:

### Source-Only Indexing

By default, ogrep indexes only source files and excludes:

| Category | Patterns |
|----------|----------|
| **Docs** | `*.md`, `*.txt`, `*.rst`, `docs/*` |
| **Config** | `*.json`, `*.yaml`, `*.yml`, `*.toml`, `*.ini` |
| **Secrets** | `.env`, `.env.*`, `secrets.*`, `credentials.*` |
| **Build** | `dist/*`, `build/*`, `vendor/*`, `*.min.js` |
| **Lock files** | `*.lock`, `package-lock.json`, `yarn.lock` |

**Skipped directories:** `.git/`, `node_modules/`, `.venv/`, `__pycache__/`, `.ogrep/`

### Optimal Chunk Size

Default: **60 lines** with 10-line overlap (tested for best relevance).

### Smart Embedding Reuse

ogrep minimizes API token usage with intelligent incremental indexing:

- **Unchanged files**: Completely skipped (no API calls)
- **Modified files**: Only changed chunks are re-embedded
- **Append-only edits**: Existing chunks reuse cached embeddings

```bash
$ ogrep index .
Indexed into .ogrep/index.sqlite
  Files: 3 indexed, 42 skipped
  Chunks: 12 total (9 reused, ~900 tokens saved)
```

**Example savings:**
| Edit Pattern | Without Reuse | With Reuse | Savings |
|--------------|---------------|------------|---------|
| Edit 1 line in 300-line file | 5 embeds | 1 embed | 80% |
| Append function to file | 5 embeds | 1 embed | 80% |
| No changes | 5 embeds | 0 embeds | 100% |

## File Filtering

### Override Default Excludes

```bash
# Include markdown files (normally excluded)
ogrep index . -i '*.md'

# Include multiple patterns
ogrep index . -i '*.md' -i '*.json'
```

### Add Extra Exclusions

```bash
# Exclude test files
ogrep index . -e 'test_*' -e '*_test.py'

# Exclude specific directories
ogrep index . -e 'fixtures/*' -e 'mocks/*'
```

## Auto-Tuning

Find the optimal chunk size for your codebase:

```bash
ogrep tune .
```

**Example output:**

```
Analyzing codebase for significant patterns...
Found 5 test patterns:
  src/auth.py:27 -> "where is the function authenticate defined..."
  src/models.py:15 -> "where is the class User defined..."
  src/api.py:42 -> "where is the function handle_request defined..."

Testing chunk size 30... accuracy=0.64 (4/5 hits)
Testing chunk size 45... accuracy=0.88 (5/5 hits)
Testing chunk size 60... accuracy=0.92 (5/5 hits)
Testing chunk size 90... accuracy=0.92 (5/5 hits)
Testing chunk size 120... accuracy=0.92 (5/5 hits)

==================================================
RESULTS
==================================================
Chunk Size   Accuracy   Hits
------------------------------
30           0.64       4/5
45           0.88       5/5
60           0.92       5/5
90           0.92       5/5
120          0.92       5/5
------------------------------

Recommended chunk size: 60 lines

To use this setting:
  ogrep index . --chunk-lines 60
```

### Apply Optimal Settings

```bash
# Auto-tune and reindex with optimal settings
ogrep tune . --apply

# Use more test samples for better accuracy
ogrep tune . -s 10
```

## Chunk Size Comparison

Results from testing on a Python codebase:

| Chunk Size | Chunks | Storage | Top Score | Notes |
|------------|--------|---------|-----------|-------|
| 30 lines | 221 | ~1.6MB | 0.373 | High precision, more storage |
| 45 lines | 100 | 832KB | 0.362 | Good balance |
| **60 lines** | 74 | ~600KB | **0.382** | **Best relevance (default)** |
| 90 lines | 52 | ~450KB | 0.350 | Larger context |
| 120 lines | 44 | 412KB | 0.309 | May miss specific functions |

## Embedding Models

Use `-m` or `--model` flag, or set `OGREP_MODEL` environment variable:

```bash
# Use model alias
ogrep index . -m large

# Use full model name
ogrep index . --model text-embedding-3-large

# Set default via environment
export OGREP_MODEL=large
ogrep index .
```

| Model | Alias | Dimensions | Price | Best For |
|-------|-------|------------|-------|----------|
| text-embedding-3-small | `small` | 1536 | $0.02/M | Most use cases (recommended) |
| text-embedding-3-large | `large` | 3072 | $0.13/M | High-accuracy, multi-language |
| text-embedding-ada-002 | `ada` | 1536 | $0.10/M | Legacy compatibility |

**Note:** Query model must match index model. Use `ogrep status` to check.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required. Your OpenAI API key |
| `OGREP_MODEL` | Default embedding model (default: `text-embedding-3-small`) |
| `OGREP_DIMENSIONS` | Default embedding dimensions (optional) |

## Multi-Repo Scope Management

Prevent cross-repo pollution with scope flags:

| Flag | Description |
|------|-------------|
| `--db PATH` | Custom database path |
| `--profile NAME` | Named profile (`.ogrep/<name>/index.sqlite`) |
| `--global-cache` | Use `~/.cache/ogrep/<hash>/index.sqlite` |
| `--repo-root PATH` | Explicit repo root |

## Example Queries

```bash
# Find where something is implemented
ogrep query "where is user authentication handled?" -n 10

# Find error handling
ogrep query "how are API errors handled?" -n 15

# Find database operations
ogrep query "database connection and queries" -n 10

# Find specific patterns
ogrep query "recursive file scanning" -n 5
```

## Development

```bash
git clone https://github.com/gplv2/ogrep-marketplace.git
cd ogrep-marketplace
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

make test    # Run tests
make lint    # Run linters
make check   # All checks
```

## Documentation

- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [CLAUDE.md](CLAUDE.md) - Developer guide for Claude Code

## License

MIT
