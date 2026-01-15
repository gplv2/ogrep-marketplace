# ogrep Quick Start

## For Users: Install and Use

### 1. Install

```bash

# Option A: pip (recommended)
pip install ogrep

# Option B: pipx 
pipx install ogrep
```

### 2. Set API Key

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

### 3. Index and Query

```bash
cd /path/to/your/repo
ogrep index . -ls
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

## For Local Models (Free, Offline)

### 1. Install LM Studio

Download from [lmstudio.ai](https://lmstudio.ai/) and launch it once.  


### 2. Setup CLI and Model

```bash
# Add CLI to PATH
~/.lmstudio/bin/lms bootstrap

# Download MiniLM (smallest, fastest, best accuracy)
lms get all-MiniLM-L6-v2 -y

# Load model and start server
lms load all-minilm-l6-v2 -y
lms server start
```

### 3. Configure ogrep

```bash
export OGREP_BASE_URL=http://localhost:1234/v1
```

### 4. Index and Query

```bash
ogrep index .   # Auto-uses minilm (best local model)
ogrep query "where is auth handled?" -n 15
```

### 5. (Optional) Benchmark Models

```bash
# Find optimal settings for your codebase
ogrep benchmark . --samples 10 --save
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
| `ogrep tune .` | Auto-tune chunk size |
| `ogrep benchmark .` | Compare all models |

## Common Flags

| Flag | Description |
|------|-------------|
| `-m MODEL` | Embedding model (small, large, minilm, nomic, bge, bge-m3) |
| `-n N` | Number of results (query) |
| `-r` | Refresh index before query |
| `-f` | Force/skip confirmation |
| `--db PATH` | Custom database path |
| `--samples N` | Test samples for tune/benchmark |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required for OpenAI models |
| `OGREP_BASE_URL` | Local server URL (enables local models) |
| `OGREP_MODEL` | Default model (auto-selects based on config) |
| `OGREP_CHUNK_LINES` | Tuned chunk size (from tune/benchmark) |
