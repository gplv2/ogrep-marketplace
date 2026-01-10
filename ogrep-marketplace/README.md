# ogrep

Local semantic grep powered by:
- **SQLite index** (`.ogrep/index.sqlite` by default)
- **OpenAI embeddings** (used only for vectorization)

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
# Faster scoring with numpy
pip install "ogrep[speed]"

# MCP server support
pip install "ogrep[mcp]"
```

## Quick Start

```bash
# Index the current directory
ogrep index .

# Semantic search
ogrep query "where is invoice status handled?" --top 15

# Check index status
ogrep status
```

## CLI Commands

### index

Index a directory (creates `.ogrep/index.sqlite`):

```bash
ogrep index .
ogrep index /path/to/repo
ogrep index . --chunk-lines 100 --overlap 20
```

### query

Semantic search over the index:

```bash
ogrep query "error handling logic" --top 20
ogrep query "database connection" --model text-embedding-3-large
```

### status

Show index statistics:

```bash
ogrep status
```

### reset

Remove the index database:

```bash
ogrep reset           # Interactive confirmation
ogrep reset --force   # No confirmation
```

### reindex

Force rebuild from scratch:

```bash
ogrep reindex .
```

### clean

Remove stale entries (deleted files):

```bash
ogrep clean           # Remove stale entries
ogrep clean --vacuum  # Also compact database
```

## Multi-Repo Scope Management

ogrep supports multiple indexing strategies to prevent cross-repo pollution:

### Default: Per-repo local index

```bash
# Index is stored at .ogrep/index.sqlite in the repo
ogrep index .
```

### Profile-based indexes

Multiple indexes per repo with different settings:

```bash
# Create different profiles
ogrep index . --profile detailed --chunk-lines 50
ogrep index . --profile compact --chunk-lines 200

# Query specific profile
ogrep query "test" --profile detailed
```

### Global cache mode

Shared cache under `~/.cache/ogrep/` keyed by repo path:

```bash
ogrep index . --global-cache
ogrep query "test" --global-cache
```

### Explicit database path

Full control over index location:

```bash
ogrep index . --db /path/to/custom.sqlite
ogrep query "test" --db /path/to/custom.sqlite
```

## SQLite Schema

The index is a single SQLite file with two tables:

- **files**: One row per indexed file (`path`, `mtime_ns`, `size`, `sha256`)
- **chunks**: One row per chunk (`file_id`, `chunk_index`, `start_line`, `end_line`, `text`, `embedding`)

## Environment Variables

- `OPENAI_API_KEY` (required): Your OpenAI API key for embeddings

## Claude Code Skill

When installed as a Claude Code plugin, the `semantic-grep` skill is available:

```
Use ogrep for meaning-based code searches:
1. If index doesn't exist: ogrep index .
2. For semantic queries: ogrep query "<question>" --top 15
3. Open top results for detailed analysis
```

## MCP Server (Optional)

If installed with the `mcp` extra:

```bash
pip install "ogrep[mcp]"
python -m ogrep.mcp
```

Exposes tools:
- `ogrep_index(path, db)` - Index a directory
- `ogrep_search(q, db, top_k)` - Semantic search

## Development

```bash
# Clone and setup
git clone https://github.com/gplv2/ogrep-marketplace.git
cd ogrep-marketplace
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
make test

# Run linters
make lint

# Format code
make fmt

# All checks
make check
```

## License

MIT
