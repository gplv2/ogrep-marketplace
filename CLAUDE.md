# CLAUDE.md - Developer Guide for Claude Code

This file provides guidance for Claude Code when working in this repository.

## Repository Overview

**ogrep** is a local semantic grep tool with:
- SQLite-based local index (no external vector DB)
- OpenAI embeddings for semantic search
- Claude Code plugin/skill integration
- Multi-repo scope fencing

## Directory Structure

```
ogrep/
├── .claude-plugin/           # Marketplace config (repo root)
│   └── marketplace.json
├── ogrep-marketplace/        # Python package
│   ├── ogrep/                # Main source code
│   │   ├── cli.py            # CLI commands
│   │   ├── db.py             # SQLite schema/connection
│   │   ├── indexer.py        # File indexing logic
│   │   ├── search.py         # Query/search logic
│   │   ├── embed.py          # OpenAI embeddings
│   │   ├── chunking.py       # Text chunking
│   │   └── mcp/              # MCP server (optional)
│   ├── plugins/ogrep/        # Claude Code plugin
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   ├── commands/         # Slash commands
│   │   └── skills/           # Skills
│   ├── tests/                # Test suite
│   └── pyproject.toml        # Package config
├── .env.example              # Environment template
├── .pre-commit-config.yaml   # Pre-commit hooks
├── .yamllint.yaml            # YAML linting config
├── Makefile                  # Development commands
└── activate.sh               # Venv activation helper
```

## Development Workflow

### Setup

```bash
# Activate virtual environment
source .venv/bin/activate
# Or use the helper
source activate.sh

# Install in editable mode with dev dependencies
pip install -e "./ogrep-marketplace[dev]"
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
| `ogrep/cli.py` | CLI entry point and all commands |
| `ogrep/indexer.py` | File walking and indexing logic |
| `ogrep/search.py` | Query execution and scoring |
| `ogrep/db.py` | SQLite schema and connection |
| `tests/conftest.py` | Pytest fixtures with OpenAI mock |

## CLI Commands

- `ogrep index .` - Index a directory
- `ogrep query "text"` - Semantic search
- `ogrep status` - Show index stats
- `ogrep reset` - Delete index
- `ogrep reindex .` - Rebuild index
- `ogrep clean` - Remove stale entries

## Scope Fencing

The tool prevents cross-repo pollution with these strategies:

1. **Default**: `.ogrep/index.sqlite` in repo root
2. **Profile**: `.ogrep/<profile>/index.sqlite`
3. **Global cache**: `~/.cache/ogrep/<hash>/index.sqlite`
4. **Explicit**: `--db /path/to/db.sqlite`

## Testing Notes

- Tests use a mock OpenAI client by default (see `conftest.py`)
- Real API tests are marked with `@pytest.mark.integration`
- Run integration tests with: `OGREP_INTEGRATION_TESTS=1 pytest -m integration`

## Plugin Structure

The Claude Code plugin is at `ogrep-marketplace/plugins/ogrep/`:

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

## Common Tasks

### Adding a new CLI command

1. Add function `cmd_<name>` in `cli.py`
2. Add parser in `main()` function
3. Add tests in `tests/test_cli.py`
4. Add command file in `plugins/ogrep/commands/<name>.md`

### Modifying the database schema

1. Update `SCHEMA` in `db.py`
2. Consider migration strategy (usually reset + reindex)
3. Update tests in `tests/test_db.py`

### Adding a new skill

1. Create `plugins/ogrep/skills/<name>/SKILL.md`
2. Define frontmatter with `name`, `description`, `allowed-tools`
3. Document skill behavior in markdown body

## Environment Variables

- `OPENAI_API_KEY` (required) - OpenAI API key for embeddings
- `OGREP_INTEGRATION_TESTS` - Set to "1" to run real API tests

## Debugging Tips

1. Check index status: `ogrep status`
2. Reset and reindex: `ogrep reindex .`
3. View database directly: `sqlite3 .ogrep/index.sqlite`
4. Check for stale files: `ogrep clean --vacuum`
