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
pip install "ogrep[speed]"   # Faster scoring with numpy
pip install "ogrep[mcp]"     # MCP server support
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

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index current directory |
| `ogrep query "text" --top N` | Semantic search |
| `ogrep status` | Show index statistics |
| `ogrep reset --force` | Delete index |
| `ogrep reindex .` | Rebuild from scratch |
| `ogrep clean --vacuum` | Remove stale entries |

## Multi-Repo Scope Management

Prevent cross-repo pollution with scope flags:

| Flag | Description |
|------|-------------|
| `--db PATH` | Custom database path |
| `--profile NAME` | Named profile (`.ogrep/<name>/index.sqlite`) |
| `--global-cache` | Use `~/.cache/ogrep/<hash>/index.sqlite` |
| `--repo-root PATH` | Explicit repo root |

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

- [QUICKSTART.md](ogrep-marketplace/QUICKSTART.md) - Quick start guide
- [CLAUDE.md](CLAUDE.md) - Developer guide for Claude Code

## License

MIT
