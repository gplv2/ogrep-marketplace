# ogrep

**Semantic grep for codebases** — local-first, SQLite-backed, and built for Claude Code Skills (not MCP).

ogrep helps you search code by **meaning**, not just keywords. It builds a local semantic index (`.ogrep/index.sqlite` by default) and retrieves the most relevant code chunks for questions like:

- *"where is authentication handled?"*
- *"how are API errors mapped to exceptions?"*
- *"where do we open DB connections and run queries?"*
- *"what kind of API key mechanism do we use?"*

**GitHub:** [github.com/gplv2/ogrep-marketplace](https://github.com/gplv2/ogrep-marketplace)
**Website:** [ogrep.be](https://ogrep.be) — quick overview

---

## What's New in v0.8.x

### v0.8.1: AST Chunking Now Default

AST-aware chunking is now **enabled by default** when tree-sitter is available. This produces semantically coherent chunks (complete functions, classes) instead of arbitrary line breaks.

- `--ast` flag removed (now default behavior)
- `--no-ast` flag added to explicitly disable
- Auto-detection: uses AST when tree-sitter is installed, falls back silently otherwise

```bash
pip install "ogrep[ast]"  # Enable AST support
ogrep index .             # AST enabled automatically
ogrep index . --no-ast    # Explicitly disable
```

### v0.8.0: Voyage AI Integration & Benchmark Findings

#### Voyage AI (Recommended for Code Search)

Voyage AI's `voyage-code-3` achieves **best search quality** in our benchmarks:

| Configuration | Hit@1 | MRR | Cost |
|---------------|-------|-----|------|
| **Voyage voyage-code-3** | **7/10** | **0.717** | $0.06/M |
| OpenAI text-embedding-3-small | 6/10 | 0.700 | $0.02/M |
| Nomic (local) + flashrank | 6/10 | 0.633 | Free |

```bash
pip install "ogrep[voyage]"
export VOYAGE_API_KEY="pa-..."
ogrep index . -m voyage-code-3
```

#### Key Finding: Skip Reranking with Quality Embeddings

**Reranking degrades results** when using high-quality embeddings:

| Embedding | Without Rerank | With Rerank | Action |
|-----------|----------------|-------------|--------|
| Voyage | **0.717 MRR** | 0.593 (-17%) | ❌ Don't rerank |
| OpenAI | **0.700 MRR** | 0.550 (-21%) | ❌ Don't rerank |
| Nomic (local) | 0.545 MRR | **0.633** (+16%) | ✅ Use reranking |

**The rule:** Reranking helps weak embeddings but hurts strong ones.

#### FlashRank as Default Reranker

When reranking is needed, FlashRank is now the default:
- **Lightweight:** ~4MB (vs ~300MB for PyTorch models)
- **Parallel-safe:** No file locking needed (ONNX runtime)
- **Fast:** ~200ms per query on CPU

### v0.7.4: Path Filtering, Summary Mode, Confidence Scoring

- **Path filtering:** `--glob "*.py"` and `--exclude "tests/*"`
- **Summary mode:** `--summarize` for file-level aggregation (~85% token savings)
- **Hybrid confidence scoring:** Combines relative position + absolute quality

### v0.7.3: Branch-Aware Indexing

- Automatic branch tracking prevents stale results when switching branches
- Cross-branch queries: `ogrep query "auth" --branch main`
- Embedding reuse across branches via content addressing

### Breaking Changes

- **v0.8.1:** `--ast` flag removed (AST is now default)
- **v0.7.2:** JSON output is now default (use `--no-json` for text)

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

**Important:** Claude Code runs bash in a non-interactive shell, so environment variables from `.bashrc`/`.zshrc`/`direnv` are **not loaded**. You must configure API keys in `.claude/settings.local.json`:

```bash
cp .claude/settings.json.example .claude/settings.local.json
# Edit with your actual API keys
```

See [SETUP.md](SETUP.md) for details.

### Optional Extras

```bash
# AST-aware chunking (recommended - enables default AST mode)
pip install "ogrep[ast]"           # Python/JS/TS/Go/Rust support
pip install "ogrep[ast-all]"       # All 13 supported languages

# Voyage AI (best search quality)
pip install "ogrep[voyage]"        # Voyage embeddings + reranking

# Reranking (only needed for local embeddings)
pip install "ogrep[rerank-light]"  # FlashRank (lightweight, recommended)
pip install "ogrep[rerank]"        # sentence-transformers (PyTorch)

# Other extras
pip install "ogrep[speed]"         # Faster scoring with numpy
pip install "ogrep[mcp]"           # MCP server support

# Combine extras
pip install "ogrep[ast,voyage]"    # AST + Voyage (best quality)
pip install "ogrep[ast,rerank-light]"  # AST + FlashRank (local use)
```

---

## Quick Start

### With Voyage AI (Best Quality)

```bash
pip install "ogrep[ast,voyage]"
export VOYAGE_API_KEY="pa-..."  # Get from https://dash.voyageai.com/

ogrep index . -m voyage-code-3             # Index with code-optimized embeddings
ogrep query "where is auth handled?" -n 10 # Semantic search (no reranking needed)
ogrep status                               # Check index stats
```

### With OpenAI (Good Quality, Lower Cost)

```bash
pip install "ogrep[ast]"
export OPENAI_API_KEY="sk-..."

ogrep index .                              # Index current directory
ogrep query "where is auth handled?" -n 10 # Semantic search (no reranking needed)
ogrep status                               # Check index stats
```

### With LM Studio (Local, Free, Offline)

```bash
pip install "ogrep[ast,rerank-light]"

# 1. Install LM Studio from https://lmstudio.ai
# 2. Download and load a model
lms get nomic-embed-text-v1.5 -y
lms load nomic-ai/nomic-embed-text-v1.5-GGUF -y
lms server start

# 3. Point ogrep to local server
export OGREP_BASE_URL=http://localhost:1234/v1

# 4. Index and query (use reranking with local embeddings)
ogrep index . -m nomic
ogrep query "database connection handling" --rerank
```

See [LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md) for detailed setup and tuning.

---

## AST-Aware Chunking (Default)

**AST chunking is now enabled by default** when tree-sitter is installed. Instead of splitting by arbitrary line counts, AST chunking respects function, class, and method boundaries for better search quality.

### Why AST Chunking Matters

Without AST (line-based chunks):
```
Lines 55-115 (one chunk):
  - End of ClassA
  - Start of ClassB  ← Semantic mixing!
  - Beginning of method foo()
```

With AST chunking (default):
```
Chunk 1: ClassA (complete)
Chunk 2: ClassB.foo() method
Chunk 3: ClassB.bar() method
```

### Usage

```bash
# Install AST support (recommended)
pip install "ogrep[ast]"           # Python/JS/TS/Go/Rust
pip install "ogrep[ast-all]"       # All 13 languages

# Index (AST enabled automatically when tree-sitter available)
ogrep index .

# Check if index uses AST
ogrep status
# Output: AST Mode: enabled

# Disable AST chunking (use line-based)
ogrep index . --no-ast
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

Cross-encoders process (query, document) pairs together, providing higher precision than bi-encoder embeddings alone. However, **reranking is not always beneficial**.

### The Rule: Reranking Helps Weak Embeddings, Hurts Strong Ones

Based on comprehensive benchmarks (10 ground-truth queries, 285 files):

| Embedding | Without Rerank | With flashrank | Recommendation |
|-----------|----------------|----------------|----------------|
| **Voyage** | **0.717 MRR** | 0.593 (-17%) | ❌ Don't rerank |
| **OpenAI** | **0.700 MRR** | 0.550 (-21%) | ❌ Don't rerank |
| **Nomic** (local) | 0.545 MRR | **0.633** (+16%) | ✅ Use reranking |

**Why reranking hurts with good embeddings:**
1. Code embeddings (Voyage, OpenAI) are already well-calibrated for code search
2. Rerankers are trained on web search data (MS MARCO), not code
3. They "second-guess" correct results and push them down

### When to Use Reranking

✅ **Use `--rerank` when:**
- Using **local embeddings** (nomic, minilm, bge)
- Searching **massive codebases** (>10K files) with noisy retrieval
- The right answer appears in results but **not in top 3**

❌ **Skip `--rerank` when:**
- Using **Voyage or OpenAI embeddings** (already optimized)
- Searching **focused codebases** (<10K files)
- Results are already good without it

### Usage

```bash
# Install reranking support (only needed for local embeddings)
pip install "ogrep[rerank-light]"  # FlashRank (recommended, parallel-safe)
pip install "ogrep[rerank]"        # sentence-transformers (PyTorch)

# With local embeddings - USE reranking
ogrep query "where is auth?" --rerank

# With Voyage/OpenAI - DON'T use reranking
ogrep query "where is auth?"  # No --rerank flag
```

### Reranking Models

| Model | Backend | Size | Speed | Best For |
|-------|---------|------|-------|----------|
| `flashrank` (default) | ONNX | ~4MB | ~200ms | **Recommended** |
| `flashrank:mini` | ONNX | ~50MB | ~300ms | Better quality |
| `voyage` | API | - | ~300ms | Long documents (32K context) |
| `minilm` | PyTorch | ~90MB | ~2s | Local, no API |
| `bge-m3` | PyTorch | ~300MB | ~30s | ❌ Too slow on CPU |

Configure via environment:
```bash
export OGREP_RERANK_MODEL=flashrank
export OGREP_RERANK_TOPN=50
```

### Parallel Safety

FlashRank models (ONNX) are **parallel-safe** and can be used by multiple processes simultaneously. PyTorch models (minilm, bge-m3) use file-based locking to prevent OOM errors in parallel AI tool sessions.

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

## Path Filtering

Filter search results to specific file patterns using `--glob` and `--exclude`:

```bash
# Include only Python files
ogrep query "auth" --glob "*.py"
ogrep query "auth" -g "*.py"

# Multiple patterns
ogrep query "auth" -g "*.py" -g "*.php"

# Recursive matching
ogrep query "auth" -g "**/*.py"

# Exclude patterns
ogrep query "auth" --exclude "tests/*"
ogrep query "auth" -x "vendor/*"

# Combine include and exclude
ogrep query "auth" -g "**/*.py" -x "tests/*" -x "vendor/*"
```

JSON output includes filter stats:
```json
{
  "stats": {
    "filter_stats": {
      "candidates_before": 50,
      "candidates_after": 23,
      "removed_percent": 54.0
    }
  }
}
```

---

## Summary Mode

Get file-level aggregation without full chunk text using `--summarize`. Reduces token usage by ~85%:

```bash
ogrep query "authentication" --summarize
```

Output:
```json
{
  "summary": true,
  "total_chunks_matched": 23,
  "files": [
    {
      "path": "src/auth/login.py",
      "chunks_matched": 4,
      "best_score": 0.47,
      "confidence": "high",
      "lines_covered": [[12, 45], [78, 120]]
    }
  ],
  "recommendation": "Use 'ogrep chunk <path>:<N>' to expand specific files"
}
```

Ideal for AI tools to scan and identify relevant files before deep-diving with `ogrep chunk`.

---

## AI Tool Integration

**All commands output JSON by default** — optimized for AI tools, scripts, and programmatic contexts.
Use `--no-json` for human-readable text output.

### JSON Output (Default)

```bash
ogrep query "database connections"
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

When querying an index and AST chunking is unavailable, JSON output includes a hint:

```json
{
  "results": [...],
  "stats": { "ast_mode": "unavailable" },
  "ast_hint": "Install AST support: pip install 'ogrep[ast]'"
}
```

### Status Check

```bash
ogrep status
```

```json
{
  "database": ".ogrep/index.sqlite",
  "status": "indexed",
  "indexed": true,
  "branch": "main",
  "branch_files": 45,
  "files": 45,
  "branches": {"main": 45},
  "chunks": 234,
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "ast_mode": true,
  "size_bytes": 2456789,
  "size_human": "2.3 MB"
}
```

### For Claude Code Skills

JSON output is now the default. The Claude Code Skill should:
- Use `--refresh` to ensure results reflect current codebase state
- Check `stats.ast_mode` and suggest `ogrep reindex .` if false (AST is default when tree-sitter is available)
- Use `--no-json` only if human-readable output is needed

---

## CLI Commands

All commands output JSON by default. Use `--no-json` for human-readable text.

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index current directory (AST enabled by default) |
| `ogrep index . --no-ast` | Index with line-based chunking |
| `ogrep index . --list` | Preview files before indexing |
| `ogrep query "text" -n 10` | Search (hybrid mode by default) |
| `ogrep query "text" --rerank` | Search with cross-encoder reranking |
| `ogrep query "text" --glob "*.py"` | Filter to Python files |
| `ogrep query "text" --summarize` | File-level summary (token-efficient) |
| `ogrep query "text" --no-json` | Human-readable output |
| `ogrep query "text" --mode semantic` | Pure semantic search |
| `ogrep query "text" --mode fulltext` | Keyword search (FTS5) |
| `ogrep query "text" --branch main` | Query a specific branch |
| `ogrep chunk "path:N" -C 1` | Get chunk with context |
| `ogrep status` | Show index statistics |
| `ogrep device` | Check GPU/CPU for reranking |
| `ogrep health` | Full database diagnostics |
| `ogrep health --vacuum` | Reclaim space and defragment |
| `ogrep health --full` | Vacuum + rebuild FTS5 + integrity check |
| `ogrep log` | Show index change history |
| `ogrep delete "path"` | Remove files from index |
| `ogrep reset -f` | Delete current branch from index |
| `ogrep reset -f --all` | Delete entire index (all branches) |
| `ogrep reindex .` | Rebuild index (AST enabled by default) |
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

**Choose your embedding source based on quality benchmarks:**

| Provider | Cost | Quality (MRR) | Reranking | Setup |
|----------|------|---------------|-----------|-------|
| **Voyage AI** (recommended) | $0.06/M | **0.717** | ❌ Skip | Add `VOYAGE_API_KEY` |
| **OpenAI API** | $0.02/M | 0.700 | ❌ Skip | Add `OPENAI_API_KEY` |
| **LM Studio** (local) | Free | 0.633 | ✅ Use flashrank | Run `lms server start` |

### Voyage AI (Recommended for Code Search)

Voyage AI's `voyage-code-3` model is specifically optimized for code and outperforms OpenAI on semantic code search benchmarks.

```bash
# Get API key from https://dash.voyageai.com/
export VOYAGE_API_KEY="pa-..."

# Index with Voyage (best quality)
ogrep index . -m voyage-code-3

# Or use the alias
ogrep index . -m voyage
```

### OpenAI (Good Quality, Lower Cost)

```bash
export OPENAI_API_KEY="sk-..."
ogrep index . -m small
```

### LM Studio (Local, Free, Offline)

```bash
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

1. **Use AST chunking** — `ogrep reindex .` for better semantic boundaries (AST is default)
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

### Voyage AI Models (Recommended for Code)

| Model | Alias | Dimensions | Price | Best For |
|-------|-------|------------|-------|----------|
| voyage-code-3 | `voyage` | 1024 | $0.06/M | **Code search (best quality)** |
| voyage-3 | `voyage-3` | 1024 | $0.06/M | General purpose |
| voyage-3-lite | `voyage-lite` | 512 | $0.02/M | Budget option |

Voyage AI models are specifically optimized for code and achieve the highest accuracy in our benchmarks (MRR 0.717).

### OpenAI Models (Cloud)

| Model | Alias | Dimensions | Price | Best For |
|-------|-------|------------|-------|----------|
| text-embedding-3-small | `small` | 1536 | $0.02/M | Good quality, low cost |
| text-embedding-3-large | `large` | 3072 | $0.13/M | High-accuracy, multi-language |
| text-embedding-ada-002 | `ada` | 1536 | $0.10/M | Legacy compatibility |

### Local Models (via LM Studio)

| Model | Alias | Dimensions | Notes |
|-------|-------|------------|-------|
| nomic-embed-text-v1.5 | `nomic` | 768 | Large context (8192 tokens) |
| all-MiniLM-L6-v2 | `minilm` | 384 | Smallest (~25MB) |
| bge-base-en-v1.5 | `bge` | 768 | Fallback option |
| bge-m3 | `bge-m3` | 1024 | Multi-lingual (100+ languages) |

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

Different models and codebases have different optimal chunk sizes. The tune command uses AST chunking by default when tree-sitter is available, matching production indexing behavior:

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

### Core Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | — |
| `VOYAGE_API_KEY` | Voyage AI API key | — |
| `OGREP_BASE_URL` | Local server URL (e.g., LM Studio) | — |
| `OGREP_MODEL` | Default embedding model | Smart default* |
| `OGREP_CHUNK_LINES` | Tuned chunk size | Model default |
| `OGREP_DIMENSIONS` | Embedding dimensions | Model default |

### Search Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OGREP_SEARCH_MODE` | Default search mode | `hybrid` |
| `OGREP_FUSION_METHOD` | Hybrid fusion method | `rrf` |
| `OGREP_HYBRID_ALPHA` | Semantic weight (if using alpha) | `0.7` |

### Reranking Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OGREP_RERANK_MODEL` | Reranking model | `flashrank` |
| `OGREP_RERANK_TOPN` | Candidates to rerank | `50` |
| `OGREP_RERANK_LOCK` | Lock file path (PyTorch models) | `~/.cache/ogrep/rerank.lock` |
| `OGREP_RERANK_LOCK_TIMEOUT` | Lock timeout in seconds | `120` |

### Voyage AI Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OGREP_VOYAGE_TIMEOUT` | API request timeout (seconds) | `120` |
| `OGREP_VOYAGE_RETRIES` | Max retries on failure | `2` |

### Confidence Thresholds

| Variable | Description | Default |
|----------|-------------|---------|
| `OGREP_CONFIDENCE_HIGH` | Threshold for "high" | `0.85` |
| `OGREP_CONFIDENCE_MEDIUM` | Threshold for "medium" | `0.70` |
| `OGREP_CONFIDENCE_LOW` | Threshold for "low" | `0.50` |

**Smart Model Default:**
- If `VOYAGE_API_KEY` is set → defaults to `voyage-code-3`
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

## Branch-Aware Indexing

ogrep tracks files per-branch to prevent stale search results when switching branches.

### How It Works

```
files table: (path, branch) → file metadata (branch-specific)
chunks table: text_sha256 → embedding (SHARED across all branches)
```

Same code on different branches shares embeddings — switching branches only embeds genuinely new code.

### Branch Detection

| Scenario | Branch Value |
|----------|--------------|
| Normal git branch | `main`, `feature/auth`, etc. |
| Detached HEAD | `detached-abc1234` |
| Non-git directory | `default` |

### Cross-Branch Queries

```bash
# Query current branch (default)
ogrep query "authentication"

# Query a specific branch
ogrep query "authentication" --branch main

# While on feature branch, find code in main
git checkout feature/new-auth
ogrep query "old auth function" --branch main
```

### Branch-Scoped Reset

```bash
# Clear only current branch (preserves other branches)
ogrep reset -f

# Clear entire database (all branches)
ogrep reset -f --all
```

### Automatic Cleanup

```bash
ogrep clean
# - Removes files for deleted branches
# - Shared embeddings are preserved if used by other branches
```

### Embedding Reuse Across Branches

| Scenario | API Calls |
|----------|-----------|
| Same file, same content | 0 (already indexed on this branch) |
| Same code on different branch | 0 (`text_sha256` matches) |
| 1 function changed | 1-2 (only changed chunks) |
| Switch main→feature→main | 0 (files already indexed on main) |

---

## Example Queries

```bash
# Find implementations
ogrep query "where is user authentication handled?" -n 10

# Find error handling
ogrep query "how are API errors handled?" -n 15 --rerank

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
