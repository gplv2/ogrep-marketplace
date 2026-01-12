# ogrep

**Semantic grep for codebases** — local-first, SQLite-backed, and built for Claude Code Skills (not MCP).

ogrep helps you search code by **meaning**, not just keywords. It builds a local semantic index (`.ogrep/index.sqlite` by default) and retrieves the most relevant code chunks for questions like:

- *"where is authentication handled?"*
- *"how are API errors mapped to exceptions?"*
- *"where do we open DB connections and run queries?"*
- *"what kind of API key mechanism do we use?"*

## What's New in v0.5.0

- **Hybrid Search** — Combines semantic understanding with keyword matching for superior results
- **Confidence Scores** — Know how much to trust each result (high/medium/low)
- **Chunk Navigation** — Expand context around any search result with `ogrep chunk`
- **JSON Output** — Structured output for AI tools and automation

---

## Real-world scenarios (what this is great at)

### 1) Rebuilding legacy systems by behavior (my primary use)
When you inherit a legacy codebase (PHP spaghetti, mixed triggers/procs, half-documented business logic), “fixing in place” often becomes a trap: every change risks regressions, and understanding intent takes forever.

ogrep supports a different approach:

- **Understand intent → extract behavior → rebuild cleanly**
- Identify *what the system does* (invoices, device provisioning, auth, state transitions, edge cases)
- Reconstruct a **behavioral spec** and implement a new, maintainable system that mimics the original outcomes — without dragging the old architecture along.

Think “software archaeology”: you’re not searching for *a string*, you’re searching for *meaning*.

### 2) Turning “token blackholes” into a cheap retrieval step
The common workflow is painful and expensive:

> grep → copy/paste huge files → LLM reads everything → repeat → burn tokens

ogrep flips that:

- You **index once** (embeddings stored in SQLite).
- Queries retrieve **top-K relevant snippets** fast.
- You only send the **small, relevant** results to an LLM *when needed*.

**Validate the claim:** ogrep itself does not need a chat LLM to work. It uses embeddings for indexing + query retrieval.

- With **local embeddings** (LM Studio), embedding cost is effectively **free**.
- With **OpenAI embeddings**, you still pay *embedding tokens* during indexing (and a tiny amount per query), but you avoid the “paste the repo into a chat model” cost explosion.
- Any *chat/completion tokens* are only spent when you choose to have an LLM interpret the retrieved snippets (e.g., inside Claude Code via the Skill).

### 3) Fast navigation through unknown repos
- Find where a feature “really” lives (even if naming is inconsistent)
- Trace flows like “request → validation → persistence → side effects”
- Discover the real entry points, glue code, and hidden coupling

### 4) Safer refactors and migrations
- Locate the real “source of truth” logic before rewriting
- Identify duplicated or divergent implementations
- Build a migration plan based on actual code paths, not guesswork

---

## Embedding Providers

**Choose your embedding source:**

| Provider | Cost | Privacy | Setup |
|----------|------|---------|-------|
| **OpenAI API** | $0.02/M tokens | Cloud | Just add `OPENAI_API_KEY` |
| **LM Studio** (local) | Free | 100% local | Run `lms server start` |

### setting up environment
```bash
# OpenAI (cloud)
export OPENAI_API_KEY="sk-..."
ogrep index . -m small

# LM Studio (local, free, offline)
export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index . -m nomic
```

### using direnv control for autoloading .env (optional)

Install **direnv** and follow the common practices, basically, your .bashrc (linux) will have this line somewhere:

```bash
eval "$(direnv hook bash)"
```

Create a .envrc file in the base dir:
```bash
# Auto-load .env when entering directory
dotenv
```

It will complain about permissions. allow it:
```bash
direnv allow
```
---

## Why ogrep?

### Local-first & simple

- Index lives in **one SQLite file** (per repo, or per profile)
- Designed to be fast to start and easy to reset
- No external services required (with local models)
- I think it's great to have this level of control and learn some AI

### Built for real dev workflows

- **Smart embedding reuse**: unchanged files skipped; only changed chunks re-embedded
- **Source-only defaults**: reduces noise, avoids indexing junk
- **Auto-tuning**: finds optimal chunk size for your codebase

### Two ways to use it

| Method | Best For |
|--------|----------|
| **CLI** (`pip`/`pipx`) | Terminal users, CI/CD, scripts (pipx install seems faulty, use pip) |
| **Claude Code Plugin** | If you live in Claude Code (recommended) |

> **Note:** This repo is primarily a Claude Code Skill + Marketplace plugin integration — not an MCP server. If you want MCP for other clients, see [Optional Extras](#optional-extras).

Please check [WORD_ABOUT_SKILLUSE.md](WORD_ABOUT_SKILLUSE.md) for adapting your project CLAUDE.md files in order to influence claude tool choice and bias for this skill. It's not an exact science it seems, I'd love getting suggestions on what works better.

---

## Installation

### Option A: pip / pipx (CLI users)

pipx doesn't work for me, pip does, marketplace install too. I would suggest to use those first.

```bash
# Install with pipx (isolated environment)
pipx install ogrep

# Or with pip
pip install ogrep
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

---

## Quick Start

### With OpenAI

```bash
export OPENAI_API_KEY="sk-..."

ogrep index .                              # Index current directory
ogrep query "where is auth handled?" -n 10 # Semantic search
ogrep status                               # Check index stats
```

### With LM Studio (Local, Free)

```bash
# 1. Install LM Studio from https://lmstudio.ai
# 2. Download and load a model
lms get nomic-embed-text-v1.5 -y
lms load nomic-ai/nomic-embed-text-v1.5-GGUF -y
lms server start

# 3. Point ogrep to local server
export OGREP_BASE_URL=http://localhost:1234/v1

# 4. Index and query
ogrep index . -m nomic
ogrep query "database connection handling" -m nomic
```

See [LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md) for detailed setup and tuning.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index current directory |
| `ogrep index . --list` | Preview files before indexing (with MIME detection) |
| `ogrep query "text" -n 10` | Search (hybrid mode by default) |
| `ogrep query "text" --mode semantic` | Pure semantic search |
| `ogrep query "text" --mode fulltext` | Keyword search (FTS5) |
| `ogrep query "text" --json` | JSON output for AI tools |
| `ogrep chunk "path:N" -C 1` | Get chunk with context |
| `ogrep status` | Show index statistics |
| `ogrep health` | Full database diagnostics |
| `ogrep health --vacuum` | Reclaim space and defragment |
| `ogrep health --full` | Vacuum + rebuild FTS5 + integrity check |
| `ogrep reset -f` | Delete index |
| `ogrep reindex .` | Rebuild from scratch (enables FTS5) |
| `ogrep clean --vacuum` | Remove stale entries |
| `ogrep models` | List available embedding models |
| `ogrep tune .` | Auto-tune chunk size for your codebase |
| `ogrep benchmark .` | Compare all models (accuracy, speed, settings) |

---

## Search Modes

ogrep supports three search modes via `--mode` (or `-M`):

| Mode | Best For | How It Works |
|------|----------|--------------|
| `hybrid` | General use (default) | Combines semantic + keyword scores |
| `semantic` | Conceptual questions | Embeddings only — "where is auth handled?" |
| `fulltext` | Exact identifiers | FTS5 keywords — "def validate_token" |

```bash
# Default: hybrid (best of both worlds)
ogrep query "user authentication" -n 10

# Pure semantic (meaning-based)
ogrep query "how are errors handled" --mode semantic

# Pure keyword (exact matches)
ogrep query "class AuthMiddleware" --mode fulltext
```

**Environment variable:** Set `OGREP_SEARCH_MODE=hybrid` (or `semantic`/`fulltext`) as default.

**Hybrid weighting:** `OGREP_HYBRID_ALPHA=0.7` controls semantic vs keyword balance (0.0-1.0).

---

## Confidence Scores

Results include confidence levels to help you decide how much to trust them:

| Confidence | Score | Guidance |
|------------|-------|----------|
| `high` | 0.85+ | Trust and use directly |
| `medium` | 0.70-0.84 | Use but verify context |
| `low` | 0.50-0.69 | Consider alternative queries |
| `very_low` | <0.50 | Likely not relevant |

```bash
ogrep query "database connections" --json
```

```json
{
  "results": [
    {
      "file": "src/db.py",
      "score": 0.89,
      "confidence": "high",
      "chunk_ref": "src/db.py:2"
    }
  ],
  "stats": {
    "confidence_summary": {"high": 3, "medium": 5, "low": 2}
  }
}
```

---

## Chunk Navigation

Found something interesting? Expand the context:

```bash
# Get chunk by reference (from query results)
ogrep chunk "src/auth.py:2"

# Include surrounding chunks
ogrep chunk "src/auth.py:2" --before 1    # 1 chunk before
ogrep chunk "src/auth.py:2" --after 1     # 1 chunk after
ogrep chunk "src/auth.py:2" --context 1   # 1 before AND after
```

This is useful when a search result looks promising but you need more context to understand it fully.

---

## Preview Mode

Before indexing, see exactly what files will be processed:

```bash
ogrep index . --list
```

Output includes:
- Files grouped by extension, sorted by size
- Binary files marked with `[BINARY: mime/type]`
- **Top 10 directories** by file count
- **Review suggestions** for files that may not be useful code

```
── .py (34 files, 179.6KB) ──
      101B  ogrep/__main__.py
    17.0KB  ogrep/commands/benchmark.py

── (no extension) (3 files, 45.2KB) ──
  [BINARY: application/x-sqlite3]   12.0KB  data
      25.2KB  Makefile

──────────────────────────────────────────────────
Would index: 35 files, 180.4KB
Excluded by detection: 1 files, 12.0KB

Top directories by file count:
    20 files  src/
    10 files  tests/

⚠ Review suggested (may distort search results):
     3.0MB  logs/app.log.old
           └─ extension '.old'
```

Use `--no-detect` to skip MIME detection for faster scans.

---

## .ogrepignore File

Create a `.ogrepignore` file for permanent exclusions (per repo):

```bash
# .ogrepignore - glob patterns like .gitignore

# Database dumps
*.sql
*.dump
migrations/*

# Generated code
*.generated.ts
codegen/*

# Legacy code
legacy/*
old/*
```

Patterns are loaded automatically. Use `-i` to override any exclusion.

---

## Embedding Models

### OpenAI Models (Cloud)

| Model | Alias | Dimensions | Price | Best For |
|-------|-------|------------|-------|----------|
| text-embedding-3-small | `small` | 1536 | $0.02/M | Most use cases (default) |
| text-embedding-3-large | `large` | 3072 | $0.13/M | High-accuracy, multi-language |
| text-embedding-ada-002 | `ada` | 1536 | $0.10/M | Legacy compatibility |

### Local Models (via LM Studio)

| Model | Alias | Dimensions | Optimal Chunks | Accuracy | Notes |
|-------|-------|------------|----------------|----------|-------|
| all-MiniLM-L6-v2 | `minilm` | 384 | 30 lines | **96%** | Best accuracy, smallest (~25MB) |
| nomic-embed-text-v1.5 | `nomic` | 768 | 30 lines | 72% | Large context window (8192 tokens) |
| bge-base-en-v1.5 | `bge` | 768 | 30 lines | 52% | Fallback option |
| bge-m3 | `bge-m3` | 1024 | 60 lines | TBD | Multi-lingual (100+ languages) |

```bash
# Use model alias (minilm auto-selected when OGREP_BASE_URL is set)
ogrep index . -m minilm

# Or set environment for persistent config
export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index .   # Auto-uses minilm
```

> **Important:** Query model must match index model. Use `ogrep status` to check.

---

## Smart Defaults

ogrep is optimized for **source code search** out of the box.

### Source-Only Indexing

By default, ogrep indexes only source files and excludes:

| Category | Examples |
|----------|----------|
| **Docs** | `*.md`, `*.txt`, `*.rst`, `docs/*` |
| **Config** | `*.json`, `*.yaml`, `*.toml`, `.editorconfig` |
| **Secrets** | `.env`, `secrets.*`, `credentials.*` |
| **Build** | `dist/*`, `build/*`, `*.min.js` |
| **Binary** | Images, fonts, media, archives |
| **Databases** | `*.sqlite`, `*.db`, `*.sql`, `*.dump` |
| **Data files** | `*.csv`, `*.tsv`, `*.xml`, `*.dat` |
| **Backups** | `*.old`, `*.bak`, `*.backup`, `*.orig`, `*~` |
| **Temp files** | `*.tmp`, `*.temp`, `*.swp` |
| **Lock files** | `package-lock.json`, `yarn.lock`, `poetry.lock` |

**Skipped directories:** `.git/`, `.svn/`, `.hg/`, `node_modules/`, `.venv/`, `__pycache__/`, `.ogrep/`

**Also skipped:** Empty files (0 bytes), duplicate symlinks, broken symlinks

### File Type Detection

ogrep uses the `file` command for MIME-type detection to catch binary files that slip through extension-based filtering (e.g., SQLite databases without `.sqlite` extension). Use `--no-detect` to disable.

### Smart Embedding Reuse

ogrep minimizes API costs with intelligent incremental indexing:

```bash
$ ogrep index .
Indexed into .ogrep/index.sqlite
  Files: 3 indexed, 42 skipped
  Chunks: 12 total (9 reused, ~900 tokens saved)
```

| Edit Pattern | Without Reuse | With Reuse | Savings |
|--------------|---------------|------------|---------|
| Edit 1 line in 300-line file | 5 embeds | 1 embed | 80% |
| Append function to file | 5 embeds | 1 embed | 80% |
| No changes | 5 embeds | 0 embeds | 100% |

---

## Auto-Tuning

Different models and codebases have different optimal chunk sizes. Find yours:

```bash
ogrep tune . -m nomic
```

```
Testing chunk size 30... accuracy=0.72 (5/5 hits)  <-- OPTIMAL
Testing chunk size 45... accuracy=0.56 (4/5 hits)
Testing chunk size 60... accuracy=0.36 (3/5 hits)
Testing chunk size 90... accuracy=0.32 (2/5 hits)
Testing chunk size 120... accuracy=0.28 (2/5 hits)

Recommended chunk size: 30 lines
```

### Save & Apply Tuning Results

```bash
# Just save for later (writes to .env)
ogrep tune . -m nomic --save

# Reindex immediately with optimal settings
ogrep tune . -m nomic --apply

# Both: save AND reindex
ogrep tune . -m nomic --save --apply
```

The `OGREP_CHUNK_LINES` environment variable persists your tuned value.

---

## Model Benchmarking

Compare all available models to find the best one for your codebase:

```bash
ogrep benchmark . -s 10
```

```
RESULTS BY MODEL
--------------------------------------------------------------------------------
Model                   Dims  Chunk/Overlap  Accuracy  Index    Query
--------------------------------------------------------------------------------
minilm                   384       30 / 15      0.96    0.89s   0.01s  *
nomic                    768       30 / 15      0.72    1.87s   0.01s
bge                      768       30 / 5       0.52    1.65s   0.01s
large                   3072       60 / 10      0.52    3.12s   0.03s
small                   1536       60 / 10      0.48    2.34s   0.02s
--------------------------------------------------------------------------------

RECOMMENDATIONS
================================================================================
* BEST OVERALL: minilm
  Accuracy: 96% | Speed: 0.89s | Cost: FREE
  Optimal: 30-line chunks, 5-line overlap

* BEST CLOUD: large
  Accuracy: 52% | Speed: 3.12s | Cost: $0.13/M tokens
```

### Benchmark Options

```bash
ogrep benchmark . --local-only     # Only test local models
ogrep benchmark . --cloud-only     # Only test OpenAI models
ogrep benchmark . --save           # Save optimal settings to .env
ogrep benchmark . --json           # Output as JSON
ogrep benchmark . -v               # Verbose per-configuration results
```

---

## File Filtering

### Include Normally-Excluded Files

```bash
# Include markdown files
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

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required for cloud) | — |
| `OGREP_BASE_URL` | Local server URL (e.g., LM Studio) | — |
| `OGREP_MODEL` | Default embedding model | Smart default* |
| `OGREP_CHUNK_LINES` | Tuned chunk size | Model default |
| `OGREP_DIMENSIONS` | Embedding dimensions | Model default |
| `OGREP_SEARCH_MODE` | Default search mode | `hybrid` |
| `OGREP_HYBRID_ALPHA` | Semantic weight in hybrid mode (0.0-1.0) | `0.7` |
| `OGREP_CONFIDENCE_HIGH` | Threshold for "high" confidence | `0.85` |
| `OGREP_CONFIDENCE_MEDIUM` | Threshold for "medium" confidence | `0.70` |
| `OGREP_CONFIDENCE_LOW` | Threshold for "low" confidence | `0.50` |

**Smart Model Default:**
- If `OGREP_BASE_URL` is set → defaults to `nomic` (local)
- Otherwise → defaults to `text-embedding-3-small` (OpenAI)

This means you can just set `OGREP_BASE_URL` and ogrep will automatically use the best local model.

---

## Multi-Repo Scope Management

Prevent cross-repo pollution:

| Flag | Description |
|------|-------------|
| `--db PATH` | Custom database path |
| `--profile NAME` | Named profile (`.ogrep/<name>/index.sqlite`) |
| `--global-cache` | Use `~/.cache/ogrep/<hash>/index.sqlite` |
| `--repo-root PATH` | Explicit repo root |

---

## Example Queries

```bash
# Find implementations
ogrep query "where is user authentication handled?" -n 10

# Find error handling
ogrep query "how are API errors handled?" -n 15

# Find database operations
ogrep query "database connection and queries" -n 10

# Find specific patterns
ogrep query "recursive file scanning" -n 5
```

---

## Documentation

- [LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md) — Local model setup, tuning, and troubleshooting
- [QUICKSTART.md](QUICKSTART.md) — Quick start guide
- [CLAUDE.md](CLAUDE.md) — Developer guide for Claude Code

---

## Development

```bash
git clone https://github.com/gplv2/ogrep-marketplace.git
cd ogrep-marketplace
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

make test    # Run tests (282 tests)
make lint    # Run linters
make check   # All checks
```

---

## License

MIT
