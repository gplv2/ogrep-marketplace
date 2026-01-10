# ogrep Quick Start

## For Users: Install and Use

### 1. Install

```bash
# Option A: pipx (recommended)
pipx install ogrep

# Option B: pip
pip install ogrep
```

### 2. Set API Key

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

### 3. Index and Query

```bash
cd /path/to/your/repo
ogrep index .
ogrep query "where is authentication handled?" -n 15
```

### 4. (Optional) Choose a Model

```bash
# List available models
ogrep models

# Use a specific model
ogrep index . -m large

# Or set default via environment
export OGREP_MODEL=large
```

---

## For Developers: Local Development

### 1. Clone and Setup

```bash
git clone https://github.com/gplv2/ogrep-marketplace.git
cd ogrep-marketplace
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Set API Key

Create `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

Or use the activation script:

```bash
source activate.sh
```

### 3. Run Commands

```bash
ogrep --help
ogrep index .
ogrep query "semantic search" -n 10
ogrep status
ogrep models
```

### 4. Run Tests

```bash
make test           # Run pytest
make lint           # Run ruff + yamllint
make check          # All checks
```

---

## For Claude Code Users

### 1. Add Marketplace

```
/plugin marketplace add gplv2/ogrep-marketplace
```

### 2. Install Plugin

```
/plugin install ogrep@ogrep-marketplace
```

### 3. Use Commands

```
/ogrep:index .
/ogrep:query "where is X implemented?"
/ogrep:status
```

---

## Command Reference

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index current directory |
| `ogrep query "text" -n N` | Semantic search |
| `ogrep status` | Show index statistics |
| `ogrep reset -f` | Delete index |
| `ogrep reindex .` | Rebuild from scratch |
| `ogrep clean --vacuum` | Remove stale entries |
| `ogrep models` | List available models |

## Common Flags

| Flag | Description |
|------|-------------|
| `-m MODEL` | Embedding model (small, large, ada) |
| `-d DIM` | Embedding dimensions |
| `-n N` | Number of results (query) |
| `-f` | Force/skip confirmation |
| `--db PATH` | Custom database path |
| `--profile NAME` | Named profile |
| `--global-cache` | Use global cache |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required. Your OpenAI API key |
| `OGREP_MODEL` | Default model (default: text-embedding-3-small) |
| `OGREP_DIMENSIONS` | Default dimensions (optional) |
