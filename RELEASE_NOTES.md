# ogrep v0.4.0 — Local Embeddings Release

**Run semantic code search completely offline. Zero API costs. Total privacy.**

## What's New

### Run Locally with LM Studio

No more API keys required! ogrep now works with local embedding models:

```bash
# Quick setup
lms get all-MiniLM-L6-v2 -y
lms load all-minilm-l6-v2 -y
lms server start

export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index . -m minilm
```

### Three Local Models to Choose From

| Model | Alias | Size | Accuracy | Best For |
|-------|-------|------|----------|----------|
| **MiniLM** | `minilm` | 25 MB | **96%** | Speed + accuracy |
| Nomic | `nomic` | 84 MB | 72% | Larger context |
| BGE | `bge` | 118 MB | 52% | Fallback option |

### Smart Tuning

Different models need different chunk sizes. Now ogrep handles it automatically:

```bash
# Find optimal settings for your codebase
ogrep tune . -m minilm --save --apply
```

The `--save` flag writes to `.env` so you don't have to remember.

## Why Upgrade?

- **Free**: Local models = $0.00 per million tokens
- **Private**: Your code never leaves your machine
- **Offline**: Works without internet
- **Fast**: No network latency

## Installation

### CLI

```bash
pipx install ogrep
# or
pip install ogrep
```

### Claude Code Plugin

```bash
/plugin marketplace add gplv2/ogrep-marketplace
/plugin install ogrep@ogrep-marketplace
```

## Documentation

- [README.md](README.md) — Quick start and overview
- [LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md) — Detailed local model setup
- [CHANGELOG.md](CHANGELOG.md) — Full technical changelog

## Links

- GitHub: https://github.com/gplv2/ogrep-marketplace
- PR: https://github.com/gplv2/ogrep-marketplace/pull/new/feat/local-embeddings
