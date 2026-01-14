# ogrep

**Semantic grep for codebases** — local-first, SQLite-backed, and built for Claude Code Skills (not MCP).

ogrep helps you search code by **meaning**, not just keywords. It builds a local semantic index (`.ogrep/index.sqlite` by default) and retrieves the most relevant code chunks for questions like:

- *"where is authentication handled?"*
- *"how are API errors mapped to exceptions?"*
- *"where do we open DB connections and run queries?"*
- *"what kind of API key mechanism do we use?"*

**GitHub:** [github.com/gplv2/ogrep-marketplace](https://github.com/gplv2/ogrep-marketplace)

---

## What's New in v0.7.0

### Major Features

- **AST-Aware Chunking** — Use `--ast` to chunk code by function/class/method boundaries instead of arbitrary line counts. This produces semantically coherent chunks that dramatically improve search accuracy for code-related queries.

- **Cross-Encoder Reranking** — Add `--rerank` to apply a cross-encoder model for high-precision ranking of search results. Solves the "right file is in top 30 but not #1" problem.

- **RRF Hybrid Fusion** — Reciprocal Rank Fusion replaces alpha weighting as the default hybrid search method. Combines results by position rather than raw scores for more robust ranking.

- **AST Mode Tracking** — Index now tracks whether AST chunking was used. Query results include hints when the index could benefit from AST mode.

### Improvements

- **Index Change History** — Track what changed with `ogrep log`, useful for AI tool integration
- **Fusion Method in JSON** — Query stats now include `fusion_method` to show which method was used
- **Better AI Tool Support** — Always use `--json` for structured output (see [AI Tool Integration](#ai-tool-integration))

### Recent (v0.6.x)

- Cross-file chunk deduplication (up to 80% embedding cost savings)
- Relative confidence scoring (compares to top result, not fixed thresholds)
- JSON output for all commands (`--json` flag)
- Graceful Ctrl-C handling with recovery messages

---

## Installation

### Option A: pip (recommended)

```bash
pip install ogrep
```

### Option B: pipx (isolated environment)

```bash
pipx install ogrep
```

Note: pipx sometimes has issues. If you encounter problems, use pip instead.

### Option C: Claude Code Marketplace + Plugin

```bash
# Add the marketplace
/plugin marketplace add gplv2/ogrep-marketplace

# Install the plugin
/plugin install ogrep@ogrep-marketplace
```

It will ask where to install. Use 'user' mode — local mode can cause path issues when working on multiple codebases.

### Optional Extras

```bash
# AST-aware chunking (recommended for code search)
pip install "ogrep[ast]"           # Python/JS/TS/Go/Rust support
pip install "ogrep[ast-all]"       # All 13 supported languages

# Cross-encoder reranking (high-precision ranking)
pip install "ogrep[rerank]"        # sentence-transformers

# Other extras
pip install "ogrep[speed]"         # Faster scoring with numpy
pip install "ogrep[mcp]"           # MCP server support

# Combine extras
pip install "ogrep[ast,rerank]"    # AST + reranking
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

## AST-Aware Chunking

**The biggest accuracy improvement for code search.** Instead of splitting by arbitrary line counts, AST chunking respects function, class, and method boundaries.

### Why AST Chunking Matters

Without AST (line-based chunks):
```
Lines 55-115 (one chunk):
  - End of ClassA
  - Start of ClassB  ← Semantic mixing!
  - Beginning of method foo()
```

With AST chunking:
```
Chunk 1: ClassA (complete)
Chunk 2: ClassB.foo() method
Chunk 3: ClassB.bar() method
```

### Usage

```bash
# Install AST support
pip install "ogrep[ast]"           # Python/JS/TS/Go/Rust
pip install "ogrep[ast-all]"       # All 13 languages

# Index with AST chunking
ogrep index . --ast

# Check if index uses AST
ogrep status
# Output: AST Mode: enabled

# Reindex existing index with AST
ogrep reindex . --ast
```

### Supported Languages

| Language | Extension | Package |
|----------|-----------|---------|
| Python | `.py` | `ogrep[ast]` |
| JavaScript | `.js` | `ogrep[ast]` |
| TypeScript | `.ts`, `.tsx` | `ogrep[ast]` |
| Go | `.go` | `ogrep[ast]` |
| Rust | `.rs` | `ogrep[ast]` |
| C | `.c`, `.h` | `ogrep[ast-all]` |
| C++ | `.cpp`, `.hpp` | `ogrep[ast-all]` |
| Java | `.java` | `ogrep[ast-all]` |
| Ruby | `.rb` | `ogrep[ast-all]` |
| PHP | `.php` | `ogrep[ast-all]` |
| C# | `.cs` | `ogrep[ast-all]` |
| Scala | `.scala` | `ogrep[ast-all]` |
| Kotlin | `.kt` | `ogrep[ast-all]` |

Files in unsupported languages fall back to line-based chunking automatically.

---

## Cross-Encoder Reranking

**Solves the "right file in top 30 but not #1" problem.** Cross-encoders process (query, document) pairs together, providing much higher precision than bi-encoder embeddings.

### How It Works

```
Query → Stage 1: Fast Retrieval (embeddings + BM25) → Top 50 candidates
                              ↓
      Stage 2: Slow Reranking (cross-encoder) → Top 10 results
```

The cross-encoder sees both query AND document together, so it can model fine-grained relationships that embeddings miss.

### Usage

```bash
# Install reranking support
pip install "ogrep[rerank]"

# Enable reranking (fetches 50, reranks, returns top -n)
ogrep query "where is authentication?" -n 10 --rerank

# Custom rerank pool size
ogrep query "where is authentication?" -n 10 --rerank-top 100
```

### Reranking Model

ogrep uses `BAAI/bge-reranker-v2-m3` by default (~300MB, auto-downloaded on first use). This model works well with code and is multilingual.

Configure via environment:
```bash
export OGREP_RERANK_MODEL=BAAI/bge-reranker-v2-m3
export OGREP_RERANK_TOPN=50
```

---

## Search Modes & Hybrid Fusion

ogrep supports three search modes via `--mode` (or `-M`):

| Mode | Best For | How It Works |
|------|----------|--------------|
| `hybrid` | General use (default) | RRF fusion of semantic + keyword |
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

### RRF Fusion (Default)

Reciprocal Rank Fusion combines results by position, not raw scores:

```
rrf_score = 1/(k + semantic_rank) + 1/(k + fulltext_rank)
```

Benefits:
- No tuning required (k=60 is standard)
- Handles score distribution differences
- Results appearing in both lists are properly boosted

### Legacy Alpha Weighting

If you prefer the old score-based fusion:
```bash
export OGREP_FUSION_METHOD=alpha
export OGREP_HYBRID_ALPHA=0.7  # 70% semantic, 30% keyword
```

---

## AI Tool Integration

**Always use `--json` when calling ogrep from AI tools, scripts, or programmatic contexts.**

### JSON Output

```bash
ogrep query "database connections" --json
```

```json
{
  "query": "database connections",
  "results": [
    {
      "rank": 1,
      "chunk_ref": "src/db.py:2",
      "path": "/home/user/project/src/db.py",
      "relative_path": "src/db.py",
      "start_line": 45,
      "end_line": 78,
      "score": 0.8923,
      "confidence": "high",
      "language": "python",
      "text": "def connect_to_database(config):\n    ..."
    }
  ],
  "stats": {
    "total_results": 10,
    "total_chunks": 234,
    "search_time_ms": 45,
    "search_mode": "hybrid",
    "fusion_method": "rrf",
    "reranked": false,
    "fts_available": true,
    "index_model": "text-embedding-3-small",
    "index_dimensions": 1536,
    "ast_mode": true,
    "confidence_summary": {"high": 3, "medium": 5, "low": 2}
  }
}
```

### AST Mode Hints

When querying an index built without AST chunking, JSON output includes a hint:

```json
{
  "results": [...],
  "stats": { "ast_mode": false },
  "hint": "Index was built without AST chunking. For better semantic boundaries, run: ogrep reindex . --ast"
}
```

### Status Check

```bash
ogrep status --json
```

```json
{
  "database": ".ogrep/index.sqlite",
  "status": "indexed",
  "indexed": true,
  "files": 45,
  "chunks": 234,
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "ast_mode": true,
  "size_bytes": 2456789,
  "size_human": "2.3 MB"
}
```

### For Claude Code Skills

The Claude Code Skill should always use:
- `--json` for structured output
- `--refresh` to ensure results reflect current codebase state
- Check `stats.ast_mode` and suggest `ogrep reindex . --ast` if false

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index current directory |
| `ogrep index . --ast` | Index with AST-aware chunking |
| `ogrep index . --list` | Preview files before indexing |
| `ogrep query "text" -n 10` | Search (hybrid mode by default) |
| `ogrep query "text" --rerank` | Search with cross-encoder reranking |
| `ogrep query "text" --json` | JSON output for AI tools |
| `ogrep query "text" --mode semantic` | Pure semantic search |
| `ogrep query "text" --mode fulltext` | Keyword search (FTS5) |
| `ogrep chunk "path:N" -C 1` | Get chunk with context |
| `ogrep status` | Show index statistics |
| `ogrep status --json` | Status as JSON |
| `ogrep health` | Full database diagnostics |
| `ogrep health --vacuum` | Reclaim space and defragment |
| `ogrep health --full` | Vacuum + rebuild FTS5 + integrity check |
| `ogrep log` | Show index change history |
| `ogrep reset -f` | Delete index |
| `ogrep reindex . --ast` | Rebuild with AST chunking |
| `ogrep clean --vacuum` | Remove stale entries |
| `ogrep models` | List available embedding models |
| `ogrep tune .` | Auto-tune chunk size |
| `ogrep benchmark .` | Compare all models |

---

## Real-world Scenarios

### 1) Rebuilding legacy systems by behavior (my primary use)

When you inherit a legacy codebase (PHP spaghetti, mixed triggers/procs, half-documented business logic), "fixing in place" often becomes a trap: every change risks regressions, and understanding intent takes forever.

ogrep supports a different approach:

- **Understand intent → extract behavior → rebuild cleanly**
- Identify *what the system does* (invoices, device provisioning, auth, state transitions, edge cases)
- Reconstruct a **behavioral spec** and implement a new, maintainable system that mimics the original outcomes — without dragging the old architecture along.

Think "software archaeology": you're not searching for *a string*, you're searching for *meaning*.

### 2) Turning "token blackholes" into a cheap retrieval step

The common workflow is painful and expensive:

> grep → copy/paste huge files → LLM reads everything → repeat → burn tokens

ogrep flips that:

- You **index once** (embeddings stored in SQLite)
- Queries retrieve **top-K relevant snippets** fast
- You only send the **small, relevant** results to an LLM *when needed*

**Validate the claim:** ogrep itself does not need a chat LLM to work. It uses embeddings for indexing + query retrieval.

- With **local embeddings** (LM Studio), embedding cost is effectively **free**
- With **OpenAI embeddings**, you still pay *embedding tokens* during indexing (and a tiny amount per query), but you avoid the "paste the repo into a chat model" cost explosion

### 3) Fast navigation through unknown repos

- Find where a feature "really" lives (even if naming is inconsistent)
- Trace flows like "request → validation → persistence → side effects"
- Discover the real entry points, glue code, and hidden coupling

### 4) Safer refactors and migrations

- Locate the real "source of truth" logic before rewriting
- Identify duplicated or divergent implementations
- Build a migration plan based on actual code paths, not guesswork

---

## Embedding Providers

**Choose your embedding source:**

| Provider | Cost | Privacy | Setup |
|----------|------|---------|-------|
| **OpenAI API** | $0.02/M tokens | Cloud | Just add `OPENAI_API_KEY` |
| **LM Studio** (local) | Free | 100% local | Run `lms server start` |

### Setting up environment

```bash
# OpenAI (cloud)
export OPENAI_API_KEY="sk-..."
ogrep index . -m small

# LM Studio (local, free, offline)
export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index . -m nomic
```

### Using direnv for autoloading .env (optional)

Install **direnv** and add to your .bashrc:

```bash
eval "$(direnv hook bash)"
```

Create a .envrc file in the base dir:
```bash
# Auto-load .env when entering directory
dotenv
```

Allow it:
```bash
direnv allow
```

---

## Confidence Scores

Results include confidence levels to help you decide how much to trust them:

| Confidence | Score | Guidance |
|------------|-------|----------|
| `high` | 0.85+ | Trust and use directly |
| `medium` | 0.70-0.84 | Use but verify context |
| `low` | 0.50-0.69 | Consider alternative queries |
| `very_low` | <0.50 | Likely not relevant |

### Tuning Confidence Thresholds

The default thresholds work well for well-documented codebases. For legacy code with sparse comments:

```bash
export OGREP_CONFIDENCE_HIGH=0.60
export OGREP_CONFIDENCE_MEDIUM=0.45
export OGREP_CONFIDENCE_LOW=0.35
```

### Understanding Low Scores

Semantic search works best when code has good comments, docstrings, or descriptive variable names. Dense implementation code with few comments tends to score lower.

**If you're getting consistently low scores:**

1. **Use AST chunking** — `ogrep reindex . --ast` for better semantic boundaries
2. **Try reranking** — `--rerank` for more accurate ordering
3. **Try code-like queries** — match the terminology in the code
4. **Use fulltext mode** — for exact identifiers: `--mode fulltext`
5. **Lower thresholds** — for legacy codebases (see above)
6. **Check chunk context** — use `ogrep chunk "path:N" -C 2` to expand

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

---

## Embedding Models

### OpenAI Models (Cloud)

| Model | Alias | Dimensions | Price | Best For |
|-------|-------|------------|-------|----------|
| text-embedding-3-small | `small` | 1536 | $0.02/M | Most use cases (default) |
| text-embedding-3-large | `large` | 3072 | $0.13/M | High-accuracy, multi-language |
| text-embedding-ada-002 | `ada` | 1536 | $0.10/M | Legacy compatibility |

### Local Models (via LM Studio)

| Model | Alias | Dimensions | Accuracy | Notes |
|-------|-------|------------|----------|-------|
| all-MiniLM-L6-v2 | `minilm` | 384 | **96%** | Best accuracy, smallest (~25MB) |
| nomic-embed-text-v1.5 | `nomic` | 768 | 72% | Large context window (8192 tokens) |
| bge-base-en-v1.5 | `bge` | 768 | 52% | Fallback option |
| bge-m3 | `bge-m3` | 1024 | TBD | Multi-lingual (100+ languages) |

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

## File Filtering

### Include Normally-Excluded Files

```bash
ogrep index . -i '*.md'             # Include markdown
ogrep index . -i '*.md' -i '*.json' # Multiple patterns
```

### Add Extra Exclusions

```bash
ogrep index . -e 'test_*' -e '*_test.py'  # Exclude tests
ogrep index . -e 'fixtures/*'              # Exclude directories
```

### .ogrepignore File

Create a `.ogrepignore` file for permanent exclusions:

```bash
# .ogrepignore - glob patterns like .gitignore
*.sql
*.dump
migrations/*
legacy/*
```

---

## Auto-Tuning

Different models and codebases have different optimal chunk sizes:

```bash
ogrep tune . -m nomic
```

```
Testing chunk size 30... accuracy=0.72 (5/5 hits)  <-- OPTIMAL
Testing chunk size 45... accuracy=0.56 (4/5 hits)
Testing chunk size 60... accuracy=0.36 (3/5 hits)

Recommended chunk size: 30 lines
```

### Save & Apply

```bash
ogrep tune . -m nomic --save        # Save to .env
ogrep tune . -m nomic --apply       # Reindex immediately
ogrep tune . -m nomic --save --apply # Both
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
| `OGREP_FUSION_METHOD` | Hybrid fusion method | `rrf` |
| `OGREP_HYBRID_ALPHA` | Semantic weight (if using alpha) | `0.7` |
| `OGREP_RERANK_MODEL` | Cross-encoder model | `BAAI/bge-reranker-v2-m3` |
| `OGREP_RERANK_TOPN` | Candidates to rerank | `50` |
| `OGREP_CONFIDENCE_HIGH` | Threshold for "high" | `0.85` |
| `OGREP_CONFIDENCE_MEDIUM` | Threshold for "medium" | `0.70` |
| `OGREP_CONFIDENCE_LOW` | Threshold for "low" | `0.50` |

**Smart Model Default:**
- If `OGREP_BASE_URL` is set → defaults to `nomic` (local)
- Otherwise → defaults to `text-embedding-3-small` (OpenAI)

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
ogrep query "how are API errors handled?" -n 15 --rerank

# Find database operations (with AST index)
ogrep query "database connection and queries" -n 10 --json

# Find specific patterns
ogrep query "recursive file scanning" -n 5
```

---

## Documentation

- [LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md) — Local model setup, tuning, and troubleshooting
- [QUICKSTART.md](QUICKSTART.md) — Quick start guide
- [CLAUDE.md](CLAUDE.md) — Developer guide for Claude Code
- [WORD_ABOUT_SKILLUSE.md](WORD_ABOUT_SKILLUSE.md) — Adapting CLAUDE.md for skill usage

---

## Development

```bash
git clone https://github.com/gplv2/ogrep-marketplace.git
cd ogrep-marketplace
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ast,rerank]"

make test    # Run tests (377 tests)
make lint    # Run linters
make check   # All checks
```

---

## License

MIT
