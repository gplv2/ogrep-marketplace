# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-01-13

### ✨ New Features

#### Reciprocal Rank Fusion (RRF) - Default Hybrid Fusion Method

Hybrid search now uses **Reciprocal Rank Fusion (RRF)** by default, replacing the previous alpha-weighted score combination. RRF is more robust because it combines results by rank position rather than raw scores.

**Why this matters:**
- Semantic similarity and BM25 scores have very different distributions
- RRF uses ranks (1st, 2nd, 3rd...) which are comparable across systems
- No hyperparameter tuning needed (k=60 is standard in literature)
- Published research shows consistent improvements over score weighting

**How RRF works:**
```
RRF score = 1/(k + semantic_rank) + 1/(k + fts_rank)

Example: Chunk ranked #1 in semantic, #5 in full-text
  = 1/(60+1) + 1/(60+5)
  = 0.0164 + 0.0154
  = 0.0318
```

**Note:** RRF scores are smaller (0.03-0.04 for top results) but the **ranking is more accurate**.

**Configuration:**
```bash
# RRF is now the default
ogrep query "search" --json

# Switch to alpha weighting (legacy)
OGREP_FUSION_METHOD=alpha ogrep query "search" --json

# Adjust RRF k parameter (rarely needed)
OGREP_RRF_K=30 ogrep query "search" --json
```

#### JSON Stats Include Fusion Method

Query JSON output now includes `fusion_method` in stats to show which method was used:

```json
{
  "stats": {
    "search_mode": "hybrid",
    "fusion_method": "rrf",
    ...
  }
}
```

#### Cross-Encoder Reranking (Optional)

Add optional reranking of search results using cross-encoder models for improved precision. Cross-encoders process (query, document) pairs together, providing more accurate relevance judgments than bi-encoders (embeddings).

**When to use reranking:**
- When the right result is often in top 30 but not #1
- When precision matters more than speed
- For AI tool integration where accuracy is critical

**Usage:**
```bash
# Install reranking support
pip install "ogrep[rerank]"

# Enable reranking (fetches top 50, reranks, returns top 10)
ogrep query "where is auth" --rerank

# Rerank specific number of candidates
ogrep query "where is auth" --rerank-top 30
```

**Two-stage retrieval:**
1. Fast retrieval: Embeddings + BM25 get top 50 candidates
2. Slow reranking: Cross-encoder reorders for precision

**Configuration:**
| Variable | Default | Description |
|----------|---------|-------------|
| `OGREP_RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | Cross-encoder model |
| `OGREP_RERANK_TOPN` | `50` | Default candidates to rerank |

**JSON output includes reranking status:**
```json
{
  "stats": {
    "reranked": true,
    ...
  }
}
```

#### AST-Aware Chunking (Optional)

Chunk code by **semantic boundaries** (functions, classes, methods) instead of arbitrary line counts. Uses tree-sitter for multi-language AST parsing.

**Why this matters:**
- Each chunk is a complete semantic unit (not split mid-function)
- Better BM25 search (function names stay with their bodies)
- Better embeddings (coherent code units)
- No more "half of class A, half of class B" chunks

**Supported languages:** Python, JavaScript, TypeScript, Go, Rust (more available with `[ast-all]`)

**Usage:**
```bash
# Install AST support (core languages)
pip install "ogrep[ast]"

# Index with AST-aware chunking
ogrep index . --ast

# Install all supported languages
pip install "ogrep[ast-all]"
```

**How it works:**
```
# Line-based chunking (default):
Chunk 1: lines 1-60 (may split class/function)
Chunk 2: lines 50-110 (overlapping, may split another)

# AST-aware chunking (--ast):
Chunk 1: class UserAuth (complete, lines 1-45)
Chunk 2: def validate_token (complete, lines 47-82)
Chunk 3: def refresh_session (complete, lines 84-120)
```

**Fallback behavior:**
- Unsupported file types → line-based chunking
- Parse errors → line-based chunking
- Very large functions → split with overlap

### 🔧 Changed

#### New Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OGREP_FUSION_METHOD` | `rrf` | Hybrid fusion: `rrf` (ranks) or `alpha` (scores) |
| `OGREP_RRF_K` | `60` | RRF rank constant (higher = smoother ranking) |
| `OGREP_RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | Cross-encoder model for reranking |
| `OGREP_RERANK_TOPN` | `50` | Default candidates to rerank |

#### Score Scale Change (Hybrid Mode)

When using hybrid search with RRF (the new default):
- **Old scores**: 0.3-0.6 range (alpha-weighted)
- **New scores**: 0.02-0.04 range (RRF formula)

This is expected—RRF scores are naturally smaller. **Confidence levels remain accurate** because they compare results to the top score.

### 📚 Documentation

- **Rewrote SKILL.md** with "swiss knife" philosophy: presents ogrep as a tool that earns its place rather than forcing usage
- Added practical patterns section with real-world examples
- Added troubleshooting section for common issues
- Updated command reference and environment variables
- Documented AST chunking and reranking features
- Added "Search Quality R&D" section to LOCAL_EMBEDDINGS_GUIDE.md

### 🧪 Testing

- Added 7 new tests for RRF scoring function
- Added 13 new tests for cross-encoder reranking
- Added 25 unit tests for AST chunking
- Added 28 integration tests for AST chunking across Python, JS, Go, Rust
- Tests verify RRF formula, edge cases, and rank ordering
- Tests verify reranking, model caching, and confidence updates
- All 365 tests passing

---

## [0.6.4] - 2026-01-12

### ✨ New Features

#### Relative Confidence Scoring (Default)

Confidence levels now use **relative scoring** by default, comparing each result to the top score instead of fixed absolute thresholds. This provides more meaningful confidence levels because cosine similarity scores for text embeddings cluster around 0.3-0.5, not uniformly across [0,1].

**Why this matters:**
- A score of 0.45 is actually in the top 15% of matches (not "very low")
- The old absolute threshold of 0.85 for "high" was rarely achievable
- Relative scoring answers: "How good is this compared to the best result?"

**New default behavior:**
```
Score Distribution (relative to top result):
├── high:     90%+ of top score
├── medium:   75-89% of top score
├── low:      50-74% of top score
└── very_low: <50% of top score
```

**Example improvement:**
```bash
# Old absolute scoring (misleading):
  1. src/auth.py:2  score=0.45 [very_low]  # Actually a great match!

# New relative scoring (accurate):
  1. src/auth.py:2  score=0.45 [high]      # Top result = high confidence
  2. src/auth.py:5  score=0.42 [high]      # 93% of top = still high
  3. src/utils.py:1 score=0.35 [medium]    # 78% of top = medium
```

**Environment variables:**
```bash
# Relative mode thresholds (as % of top score, default)
export OGREP_RELATIVE_HIGH=0.90    # 90% of top score
export OGREP_RELATIVE_MEDIUM=0.75  # 75% of top score
export OGREP_RELATIVE_LOW=0.50     # 50% of top score

# Switch to absolute mode if needed
export OGREP_CONFIDENCE_MODE=absolute

# Absolute thresholds (calibrated for typical embeddings)
export OGREP_CONFIDENCE_HIGH=0.50   # Was 0.85
export OGREP_CONFIDENCE_MEDIUM=0.40 # Was 0.70
export OGREP_CONFIDENCE_LOW=0.30    # Was 0.50
```

### 🔧 Changed

#### Absolute Confidence Thresholds Recalibrated

The absolute thresholds (used when `OGREP_CONFIDENCE_MODE=absolute`) have been recalibrated based on actual embedding score distributions:

| Level | Old Threshold | New Threshold | Reason |
|-------|---------------|---------------|--------|
| high | 0.85 | 0.50 | Scores >0.50 are in top 10% |
| medium | 0.70 | 0.40 | P90 of typical results |
| low | 0.50 | 0.30 | Still meaningful matches |

This was based on analysis showing:
- Median pairwise similarity: 0.31
- P90: 0.48, P95: 0.53, P99: 0.65
- Scores above 0.50 are excellent matches

### 📚 Documentation

- Updated SKILL.md with expanded quick examples at top
- Added common patterns table for quick reference
- Enhanced chunk navigation documentation
- Updated CLAUDE.md with relative confidence explanation
- Updated LOCAL_EMBEDDINGS_GUIDE.md troubleshooting section

### 🧪 Testing

- Added 10 new tests for relative confidence scoring
- Tests verify both relative and absolute mode behavior
- All tests independent of user environment variables

## [0.6.3] - 2026-01-12

### ✨ New Features

#### JSON Output for All Commands

Every ogrep command now supports `--json` for structured output, making AI tool integration seamless:

| Command | JSON Output |
|---------|-------------|
| `ogrep index . --json` | `{status, files_indexed, chunks_total, chunks_reused, tokens_saved, model}` |
| `ogrep status --json` | `{indexed, files, chunks, model, dimensions, size_bytes, size_human}` |
| `ogrep clean --json` | `{status, removed_count, removed_paths, vacuumed}` |
| `ogrep reset -f --json` | `{status, database, removed, size_bytes, size_human}` |
| `ogrep reindex . --json` | `{status, files_indexed, chunks_total, chunks_embedded, model}` |
| `ogrep health --json` | `{tables, dedup_stats, fts5, sqlite_info, integrity, operations}` |
| `ogrep models --json` | `{models[], current_model, env_vars}` |
| `ogrep tune . --json` | `{recommended_chunk_lines, results[], settings}` |

Previously only `query`, `chunk`, and `benchmark` had JSON support.

#### Query Input Validation

ogrep now validates query length before making API calls, preventing expensive embedding requests for invalid queries:

```bash
ogrep query ""
# Error: Query too short: '' (0 chars). Minimum is 2 characters.
```

JSON error response includes `error_code` for programmatic handling:
```json
{"error": "Query too short...", "error_code": "QUERY_TOO_SHORT"}
```

#### YAML Files Now Indexed by Default

Removed `*.yaml` and `*.yml` from `DEFAULT_EXCLUDES`. Configuration files are now searchable:

- CI/CD pipelines (GitHub Actions, GitLab CI)
- Kubernetes manifests
- Docker Compose files
- Application configuration

### 🔧 Changed

#### Plugin Descriptions Enhanced

Updated `plugin.json` and `marketplace.json` with comprehensive descriptions including all search modes (semantic, fulltext, hybrid) and key features.

#### Improved Test Robustness

Confidence level tests now use actual threshold constants instead of hardcoded values, making tests work correctly regardless of `OGREP_CONFIDENCE_*` environment variable settings.

### 📚 Documentation

- Updated all plugin command markdown files with `--json` flag documentation
- Enhanced SKILL.md with complete search capabilities reference
- Added JSON output examples for every command
- Updated CLAUDE.md with new CLI capabilities

### 🧪 Testing

- 283 tests passing
- Fixed 3 confidence level tests that failed with custom environment thresholds

## [0.6.0] - 2026-01-12

### ✨ New Features

#### Graceful Ctrl-C Handling Across All Commands

All commands now handle keyboard interrupts gracefully instead of showing Python tracebacks:

```bash
ogrep index .
# Press Ctrl-C...
# Interrupted by user (Ctrl-C).
# Partial progress may have been saved to the index.
# Run 'ogrep index .' again to continue from where you left off.
```

**Commands with Ctrl-C handling:**
- `ogrep index` (both regular and `--list` mode)
- `ogrep reindex`
- `ogrep query --refresh`
- `ogrep benchmark`
- `ogrep tune` (both test loop and `--apply`)
- `ogrep health` (vacuum, rebuild-fts, integrity)
- `ogrep clean`

All commands return exit code 130 (standard SIGINT) on interrupt.

#### Tunable Confidence Thresholds and Hybrid Alpha

For legacy or sparse codebases where default thresholds produce too many "very_low" results, you can now tune the scoring:

**Confidence thresholds** (via environment variables):
```bash
# Lower thresholds for sparse codebases
export OGREP_CONFIDENCE_HIGH=0.60    # default: 0.85
export OGREP_CONFIDENCE_MEDIUM=0.45  # default: 0.70
export OGREP_CONFIDENCE_LOW=0.35     # default: 0.50
```

**Hybrid search balance** (semantic vs keyword weight):
```bash
# Favor keyword matching for identifier-heavy searches
export OGREP_HYBRID_ALPHA=0.5  # default: 0.7 (70% semantic, 30% keyword)
```

### 🐛 Fixes

#### Fixed --refresh Using Wrong Model (Dimension Mismatch Crash)

The `ogrep query --refresh` command was using CLI default model instead of the index's actual model, causing dimension mismatch crashes when indexes were built with a different model than the default.

**Before (broken):**
```
$ ogrep query "test" --refresh
ValueError: shapes (1536,) and (768,) not aligned: 1536 (dim 0) != 768 (dim 0)
```

**After (fixed):**
- Query now reads the index's model/dimensions BEFORE refresh
- Uses the index's model for incremental reindex, not CLI defaults
- Shows warning if user specified a different model with `--refresh`

#### Mixed Dimensions Detection for Corrupted Indexes

Added early detection for indexes corrupted with mixed embedding dimensions. This can happen if `--refresh` was accidentally run with a different model before the fix above.

**Before:** Cryptic numpy shape error deep in the code
**After:** Clear, actionable error message:
```
ValueError: Corrupted index: mixed dimensions detected ([768, 1536]).
This can happen if --refresh was run with a different model.
Run 'ogrep reset -f && ogrep index .' to rebuild.
```

### 🔧 Changed

#### Refactored CLI Argument Builders

Extracted common argument patterns from `cli.py` to new `ogrep/commands/_arg_builders.py` module:

| Function | Arguments | Used By |
|----------|-----------|---------|
| `add_model_args()` | `--model`, `--dimensions` | index, query, reindex, tune |
| `add_indexing_args()` | `--chunk-lines`, `--overlap`, `--max-bytes`, `-e`, `-i` | index, reindex |
| `add_benchmark_args()` | `--samples`, `--models`, `--local-only`, etc. | benchmark |

This reduces code duplication and makes argument patterns consistent across commands.

### ✨ New Features

#### Cross-File Chunk Deduplication

Identical text chunks across different files now share embeddings, saving API costs:

```bash
# Two files with identical headers, imports, or utility functions
# Only one embedding is generated, reused across both files
ogrep index .
# Output: Chunks: 68 total (32 reused from other files, ~3200 tokens saved)
```

**How it works:**
- Chunks are identified by their `text_sha256` hash
- When indexing a new file, ogrep checks if identical chunks exist anywhere in the index
- Matching chunks reuse existing embeddings (same model + dimension required)
- Database index on `text_sha256` provides O(log n) lookups

**Expected savings:**
- Duplicate license headers: Indexed once, reused everywhere
- Common imports: `from __future__ import annotations` shares embeddings
- Utility files copied across modules: Deduplicated automatically
- Two 1000-line files differing by 10 lines: 49% savings (68 vs 132 embeddings)

**New IndexStats fields:**
- `chunks_reused_global`: Embeddings reused from other files
- `chunks_reused_local`: Embeddings reused from same file (existing behavior)
- `dedup_ratio`: Percentage of chunks that were deduplicated

**Model consistency check:**
- Index enforces single model per database
- Error if querying/indexing with different model than existing chunks
- Use `ogrep reset` to start fresh with a new model

#### Dedup Stats in Health Command

The `ogrep health` command now displays cross-file deduplication statistics:

```
── Dedup Stats ──
  Total chunks: 217
  Unique hashes: 215
  Deduplicated: 2 (0.9% embedding savings)
```

Shows how many chunks share the same text hash across files, indicating embedding storage savings from deduplication.

#### Per-Model Batch Size Limits

Added `context_tokens` and `max_batch_size` to model definitions to prevent context overflow and optimize throughput:

| Model | Context | Max Batch | Default |
|-------|---------|-----------|---------|
| minilm | 256 | 16 | 16 |
| bge | 512 | 16 | 16 |
| nomic | 8192 | 32 | 16 |
| bge-m3 | 8192 | 32 | 16 |
| OpenAI (all) | 8191 | 2048 | 200 |

- **Smart defaults**: Local models default to 16, OpenAI defaults to 200
- **Auto-tuning**: Tests appropriate batch sizes per model type
- **Environment override**: `OGREP_BATCH_SIZE` capped to model's max
- OpenAI sees 38x speedup at batch 200 vs serial mode

#### Token-Aware Batching with Auto-Retry

Embedding batches now respect model context limits with automatic recovery:

```
# Upfront estimation prevents most overflows
Text truncated from ~10304 tokens to ~7371 tokens to fit context window

# If estimation is off, auto-retry kicks in
Context overflow (9047 > 8192 tokens). Truncating to 77% and retrying...
```

**How it works:**
- Estimates tokens per chunk (~3 chars/token for code)
- Splits batches to stay under model's `context_tokens` limit (with 10% safety margin)
- Oversized single chunks are automatically truncated with a warning
- **Auto-retry**: If OpenAI still returns 400, parses error, truncates more, retries (up to 3x)
- Works for both OpenAI and local models

**Token limits by model:**

| Model | Context Tokens | Max Batch Size |
|-------|----------------|----------------|
| OpenAI (all) | 8,191 | 2,048 |
| nomic | 8,192 | 32 |
| bge-m3 | 8,192 | 32 |
| minilm | 256 | 16 |
| bge | 512 | 16 |

**No configuration needed** — token-aware batching and auto-retry are automatic.

#### Friendly Model Mismatch Errors

Model mismatch errors now show helpful guidance instead of Python tracebacks:

```
Error: Model mismatch: index uses 'text-embedding-3-small' but requested 'nomic-embed-text-v1.5'.

Note: OGREP_BASE_URL is set to 'http://localhost:1234/v1'
      This defaults to 'nomic-embed-text-v1.5' for local models.
      Unsetting it will default to OpenAI (text-embedding-3-small).

Options:

  1. Use the same model as the existing index:
     unset OGREP_BASE_URL  # defaults to OpenAI
     ogrep index .

  2. Switch to new model (rebuilds entire index):
     ogrep reindex . --force

  3. Start fresh with new model:
     ogrep reset -f
     ogrep index .
```

### 🔧 Changed

- Default batch size for OpenAI increased from 16 to 200 (38x faster)
- Auto-tune now tests 7 steps from 64 to 2048 for OpenAI models
- `OGREP_BATCH_SIZE` now respects model's `max_batch_size` limit
- Batching now respects both count limits AND token limits

### 🐛 Fixes

- **Context overflow crash fixed**: Large code chunks no longer crash indexing with "maximum context length" errors. Batches are automatically split to respect model token limits.

## [0.5.0] - 2026-01-12

### ✨ New Features

#### Database Health & Repair Command

New `ogrep health` command for comprehensive database diagnostics and repair:

```bash
ogrep health                 # Full diagnostic output
ogrep health --vacuum        # Reclaim space and defragment
ogrep health --rebuild-fts   # Rebuild FTS5 index
ogrep health --integrity     # Full integrity check
ogrep health --full          # All repairs (vacuum + rebuild-fts + integrity)
```

Diagnostic output includes:
- Table sizes and row counts
- Index definitions
- SQLite info (version, journal mode, page stats, freelist)
- FTS5 statistics (token counts, unique terms)
- Quick integrity check by default

#### Hybrid Search (Phase 2)

Combines semantic embeddings with FTS5 keyword matching for superior search results:

```bash
ogrep query "authenticate user" --mode hybrid --json
```

- **Three search modes**: `semantic`, `fulltext`, `hybrid` (default)
- **FTS5 integration**: SQLite full-text search with BM25 scoring
- **Configurable weighting**: `OGREP_HYBRID_ALPHA` controls semantic vs keyword balance
- **Graceful fallback**: Falls back to semantic if FTS5 unavailable
- **New env vars**: `OGREP_SEARCH_MODE`, `OGREP_HYBRID_ALPHA`

#### Chunk Navigation (Phase 2)

New `ogrep chunk` command for expanding context around search results:

```bash
ogrep chunk "src/auth.py:2"              # Get chunk by reference
ogrep chunk "src/auth.py:2" --before 1   # + 1 chunk before
ogrep chunk "src/auth.py:2" --after 1    # + 1 chunk after
ogrep chunk "src/auth.py:2" --context 1  # + 1 before AND after
```

- **chunk_ref in results**: Query output now includes `chunk_ref` (e.g., `src/auth.py:2`)
- **chunk_id exposed**: Internal chunk ID for programmatic access
- **Context flags**: `-B`, `-A`, `-C` for before/after/context chunks
- **JSON output**: Structured output with requested chunk and neighbors

#### Confidence Scoring (Phase 3)

Human-readable confidence levels help Claude decide how much to trust results:

| Confidence | Score Range | Guidance |
|------------|-------------|----------|
| `high` | 0.85+ | Trust and use directly |
| `medium` | 0.70-0.84 | Use but verify with context |
| `low` | 0.50-0.69 | Consider alternative queries |
| `very_low` | <0.50 | Likely not relevant |

- **confidence field**: Added to each result in JSON output
- **confidence_summary**: Distribution in stats (`{"high": 3, "medium": 5, ...}`)
- **Human-readable**: Shows in text output as `score=0.85 (high)`
- **Configurable thresholds**: `OGREP_CONFIDENCE_HIGH`, `OGREP_CONFIDENCE_MEDIUM`, `OGREP_CONFIDENCE_LOW`

### 🔧 Improvements

#### Batch Chunking for Local Embedding Servers

Embedding requests to local servers (LM Studio) are now automatically batched to prevent crashes and improve throughput:

```bash
export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index .  # Automatically batches large requests
```

- **Auto-tuning**: Tests batch sizes 8, 16, 32, 64, 96 and picks the fastest
- **Crash prevention**: Prevents "Model was unloaded while request was in queue" errors
- **Session caching**: Optimal batch size is cached per session
- **Override**: Set `OGREP_BATCH_SIZE` env var to force a specific batch size
- **Smart threshold**: Only batches when >32 texts (small requests sent at once)

#### Model-Specific Overlap Defaults

Each embedding model now has its own optimal overlap setting based on benchmark results:

| Model | Chunk Size | Overlap | Why |
|-------|------------|---------|-----|
| nomic | 30 lines | **15 lines** | Large context window (8192 tokens) benefits from more overlap |
| minilm | 30 lines | **15 lines** | Small context needs overlap to preserve boundaries |
| bge | 30 lines | **5 lines** | Prefers minimal overlap |
| bge-m3 | 60 lines | **10 lines** | Moderate overlap for larger chunks |
| OpenAI | 60 lines | **10 lines** | Default for cloud models |

- **New env var**: `OGREP_OVERLAP_LINES` to override model defaults
- **New function**: `get_optimal_overlap(model)` returns tuned overlap
- **CLI updated**: `--overlap` now shows model-specific defaults in help

#### Default Local Model Changed to Nomic

When `OGREP_BASE_URL` is set (local LM Studio), ogrep now defaults to `nomic` instead of `minilm`:

- **nomic**: 768D embeddings, 8192 token context window — no truncation
- **minilm**: 384D embeddings, 256 token limit — truncates longer chunks

MiniLM showed higher accuracy in benchmarks (96% vs 88%), but this was misleading because chunks were being truncated. Nomic provides more reliable results for real-world code.

#### Enhanced `--list` Output with Breakdowns

The `ogrep index --list` command now shows summary tables:

```
Breakdown by extension:
  Extension         Files       Size      %
  --------------- ------- ---------- ------
  .py                  38    266.7KB  99.7%
  .sh                   1       809B   0.3%

Breakdown by file type:
  Type              Files       Size      %
  --------------- ------- ---------- ------
  text                 39    267.5KB 100.0%
  application           2     12.0KB   5.0%
```

- **By extension**: Count, size, and percentage for each file extension
- **By file type**: MIME type categories (text, application, etc.) when detection is enabled

#### Enhanced JSON Output

Query JSON output now includes:
- `chunk_ref`: Human-readable reference (e.g., `src/auth.py:2`)
- `chunk_id`: Internal database ID
- `confidence`: Human-readable confidence level
- `confidence_summary`: Distribution in stats
- `search_mode`: Active search mode
- `fts_available`: Whether FTS5 was available

#### Database Schema

- **FTS5 virtual table**: `chunks_fts` for full-text search
- **Sync triggers**: Automatic FTS index maintenance on insert/update/delete
- **`rebuild_fts5()` function**: Rebuild FTS index from existing chunks
- **`has_fts5()` function**: Check FTS5 availability

### 📦 New Files

- `ogrep/commands/health.py` - Database health and repair command
- `ogrep/commands/chunk.py` - Chunk navigation command
- `plugins/ogrep/commands/health.md` - Health command plugin
- `plugins/ogrep/commands/chunk.md` - Chunk command plugin
- `tests/test_health_command.py` - Health command tests (7 tests)
- `tests/test_chunk_command.py` - Chunk command tests (12 tests)
- `tests/test_hybrid_search.py` - Hybrid search tests (12 tests)
- `docs/EMBEDDING_PERFORMANCE_TEST_PLAN.md` - Test plan for local embedding performance

### 🐛 Fixes

- **Single file indexing path resolution**: Fixed crash when indexing a single file (e.g., `ogrep index file.py`) where `.ogrep` directory was incorrectly created inside the file path. Now correctly uses the parent directory.

- **Empty input handling**: `embed_texts([])` now returns empty results `([], 0)` instead of asserting, matching expected behavior for edge cases.

## [0.4.5] - 2026-01-11

### ✨ New Features

#### File Type Detection with `file` Command

ogrep now uses the system `file` command for accurate MIME-type detection, catching binary files that slip through extension-based filtering:

```bash
ogrep index . --list
```

Output now shows detection results:
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
```

- Uses `file --mime-type -b` for robust detection
- Processes in batches of 500 for large repos (30K+ files)
- Falls back to null-byte detection if `file` command unavailable
- Use `--no-detect` to disable MIME detection for faster scans

#### `.ogrepignore` File Support

Create a `.ogrepignore` file in your repo root for persistent exclude patterns:

```bash
# .ogrepignore
*.sql
migrations/*
legacy/*
*.generated.ts
```

Patterns use glob syntax (like `.gitignore`). Loaded automatically on every index operation.

#### Preview Mode with `--list`

See exactly what files will be indexed before committing:

```bash
ogrep index . --list
```

Features:
- Files grouped by extension, sorted by size (biggest last)
- Binary files marked with `[BINARY: mime/type]`
- Summary of indexable vs excluded files
- **Top 10 directories by file count** — helps identify where to focus
- **Largest indexable files** — spot potential problems
- **Review suggestions** — flags files that pass MIME detection but may not be useful code

#### Review Suggestions for Non-Code Files

The `--list` output now includes a "Review suggested" section for files that:
- Have extensions like `.log`, `.old`, `.bak`, `.dump`, `.csv`
- Have filenames suggesting logs/backups (e.g., `*.log.old`, `*_backup`)
- Are large (>500KB) without code extensions

These files pass MIME detection but may distort search results. Add patterns to `.ogrepignore` to exclude them.

### 🔧 Improvements

#### Expanded Default Exclusions

New patterns added to `DEFAULT_EXCLUDES`:

| Category | New Patterns |
|----------|--------------|
| **Temp files** | `*.tmp`, `*.temp` |
| **Backups** | `*.old`, `*.bak`, `*.backup`, `*.orig`, `*.swp`, `*~` |
| **Data files** | `*.csv`, `*.tsv`, `*.sqlt`, `*.dat`, `*.xml` |
| **Database** | `*.dump` (added to existing `*.sql`, `*.sqlite`, etc.) |

#### Batched File Detection

File type detection now processes files in batches of 500 to handle large repositories (30K+ files) without hitting command-line length limits or timeouts.

#### Smart File Skipping

- **Empty files** (0 bytes) are now skipped automatically
- **Duplicate symlinks** pointing to the same real path are deduplicated
- **Broken symlinks** are skipped gracefully (no errors)

#### Additional Skipped Directories

Added `.svn` and `.hg` (Mercurial) to `DEFAULT_SKIP_DIRS` alongside `.git`.

### 📚 Documentation

- Updated CLAUDE.md with new features and default excludes
- Added `.ogrepignore` syntax documentation
- Documented `--list` and `--no-detect` flags

### 🧪 Testing

- 182 tests passing
- New tests for file type detection (`test_filetype.py`)
- Updated version assertion in test suite

## [0.4.3] - 2026-01-11

### 🐛 Fixes

- **CI tests now pass without API keys**: Fixed test suite failing in GitHub Actions due to missing `OPENAI_API_KEY`. The mock fixture now properly sets a fake API key so `require_embedding_config()` passes before the mock client is used

### 📚 Documentation

- Added critical warning to version bump guide about not modifying marketplace JSON structure (only version numbers)

## [0.4.2] - 2026-01-11

### 📚 Documentation

- **Developer guide**: Added version bump checklist to CLAUDE.md to ensure all 7 version files are updated consistently during releases

## [0.4.1] - 2026-01-11

### 🔧 Improvements

- **Smarter Claude Code integration**: The semantic-grep skill now activates proactively when you ask conceptual questions like "where is X handled?" or "how does Y work?" — no need to explicitly request semantic search

### 🐛 Fixes

- **Clear error when API not configured**: Commands now fail immediately with helpful guidance when neither `OPENAI_API_KEY` nor `OGREP_BASE_URL` is set, instead of silently producing misleading output like "285 files skipped"

- **Fixed PyPI installation**: Removed invalid classifier that was blocking `pip install` from source

## [0.4.0] - 2026-01-11 — Local Embeddings

**Run semantic code search completely offline. Zero API costs. Total privacy.**

### ✨ New Features

#### Run Locally with LM Studio

No more API keys required! ogrep now works with local embedding models through LM Studio's OpenAI-compatible API.

```bash
lms get all-MiniLM-L6-v2 -y
lms load all-minilm-l6-v2 -y
lms server start

export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index .   # Auto-uses minilm
```

#### Four Local Models to Choose From

| Model | Alias | Accuracy | Index Time | Best For |
|-------|-------|----------|------------|----------|
| Nomic | `nomic` | **88%** | 33.5s | Highest accuracy |
| BGE | `bge` | **88%** | 21.6s | Accuracy + speed |
| **MiniLM** | `minilm` | 84% | **5.8s** | Speed (6x faster, recommended) |
| BGE-M3 | `bge-m3` | 76% | 81.5s | Multi-lingual (100+ languages) |

All local models outperform OpenAI cloud models (48-52%) on code search tasks.

#### Model Benchmarking

Compare all models head-to-head with the new benchmark command:

```bash
ogrep benchmark . -s 10
```

Tests accuracy, speed, and optimal chunk/overlap settings across all available models. Includes warnings about time and API credit consumption for large repos.

#### Smart Tuning with Auto-Save

Different models need different chunk sizes. Now ogrep handles it automatically and remembers your settings:

```bash
ogrep tune . -m minilm --save --apply
```

The `--save` flag writes optimal settings to `.env` so you don't have to remember.

### 🔧 Improvements

- **Smart Model Default**: When `OGREP_BASE_URL` is set (local server), ogrep now defaults to `minilm` automatically—no need for `-m` flag on every command
- **Model-Specific Defaults**: Each local model now has tuned chunk size defaults based on comprehensive benchmarking (all models: 30-line chunks except BGE-M3: 60 lines)
- **OGREP_CHUNK_LINES**: New environment variable to persist your tuned chunk size across sessions
- **Timing Infrastructure**: `embed_texts()` now optionally returns elapsed time via `return_timing=True`
- **Overlap Testing**: Benchmark tests different overlap values (5, 10, 15 lines) alongside chunk sizes
- **New API Function**: `get_optimal_chunk_lines(model)` returns the chunk size (env var > model default)
- **Faster Benchmarks**: Reduced default test configurations from 20 to 9 per model

### 📚 Documentation

- Overhauled README with local model quick start and provider comparison
- New `LOCAL_EMBEDDINGS_GUIDE.md` with step-by-step LM Studio setup for macOS/Linux/Windows
- Comprehensive analysis of why local models outperform cloud models for code retrieval
- Added 6-model benchmark comparison (MiniLM, Nomic, BGE, BGE-M3, OpenAI small, OpenAI large)
- Updated CLAUDE.md with local model setup and chunk tuning section

### 🧪 Testing

- 151 tests passing
- New test files: `test_benchmark.py`, `test_embed.py`, `test_models.py`, `test_search.py`, `test_query_command.py`

## [0.3.4] - 2026-01-10

### Added

- **Refresh Command**: New `/ogrep:refresh` slash command for manually refreshing the index before queries. Runs incremental reindex on changed files.

## [0.3.3] - 2026-01-10

### Added

- **Query Refresh Flag**: New `--refresh` (`-r`) flag for the query command that automatically checks for changed files and reindexes before searching:
  ```bash
  ogrep query "where is auth handled" --refresh
  ```
  This ensures AI tools always get accurate results reflecting the current codebase state.

- **Stale File Detection**: Query command can now detect files that have been modified or deleted since last indexing by comparing mtime/size.

- **Claude Code Hook Documentation**: Added documentation for configuring Claude Code hooks to auto-reindex after file edits as an alternative to `--refresh`.

### Changed

- **Skill Updated**: The semantic-grep skill now uses `--refresh` by default to prevent stale results.
- **Plugin Query Command**: Updated to use `--refresh` flag.

### Documentation

- New "AI Tool Integration" section in CLAUDE.md explaining `--refresh` flag and hook configuration.
- Added 2 new tests for stale file detection (42 tests total).

## [0.3.2] - 2026-01-10

### Fixed

- **Test Cleanup**: Removed unused imports and variables in embedding reuse tests

## [0.3.1] - 2026-01-10

### Added

- **Expanded Default Exclusions**: More comprehensive filtering for source-only indexing:
  - **Directories**: `venv/`, `.githooks/`, `storage/` (Laravel), `.mypy_cache/`, `.tox/`, `.pytest_cache/`, `.ruff_cache/`
  - **Git metadata**: `.gitignore`, `.gitattributes`, `.gitmodules`, `.gitkeep`
  - **Images**: `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.webp`, `*.ico`, `*.bmp`, `*.tiff`, `*.psd`
  - **Fonts**: `*.woff`, `*.woff2`, `*.ttf`, `*.otf`, `*.eot`
  - **Media**: `*.mp3`, `*.mp4`, `*.wav`, `*.avi`, `*.mov`, `*.webm`
  - **Archives**: `*.zip`, `*.tar`, `*.gz`, `*.rar`, `*.7z`
  - **Databases**: `*.sqlite`, `*.sqlite3`, `*.db`
  - **Logs**: `*.log`, `logs/*`
  - **Python packages**: `*.dist-info/*`, `*.pth`, `py.typed`
  - **Config**: `.editorconfig`, `.phpunit.result.cache`

### Fixed

- **Non-Interactive Reset**: `ogrep reset` now requires `-f` flag when running non-interactively (e.g., from Claude Code) instead of crashing with EOFError

## [0.3.0] - 2026-01-10

### Added

- **Smart Embedding Reuse**: Save ~80% on API tokens when re-indexing! When files change, ogrep now reuses embeddings for unchanged chunks instead of re-embedding everything.
  ```
  Files: 3 indexed, 42 skipped
  Chunks: 12 total (9 reused, ~900 tokens saved)
  ```

- **Auto-Tuning**: New `ogrep tune` command finds the optimal chunk size for your codebase:
  - Tests chunk sizes 30, 45, 60, 90, 120 lines
  - Samples real function/class definitions as test patterns
  - Reports accuracy scores and recommends best setting
  - `ogrep tune . --apply` to auto-reindex with optimal settings

- **Smart Source-Only Defaults**: ogrep now focuses on source code by default:
  - Excludes: docs (`*.md`), config (`*.json`, `*.yaml`), build outputs, lock files
  - Excludes secrets: `.env`, `credentials.*`, `secrets.*`
  - Skips: `.git/`, `node_modules/`, `.venv/`, `__pycache__/`

- **File Filtering Flags**:
  - `-e/--exclude PATTERN`: Add patterns to exclude (e.g., `-e 'test_*'`)
  - `-i/--include PATTERN`: Override default excludes (e.g., `-i '*.md'` to index markdown)

- **Indexing Statistics**: See what happened during indexing:
  - Files indexed vs skipped
  - Chunks embedded vs reused
  - Estimated tokens saved

### Fixed

- **Model Mismatch Error**: Clear error message when querying with wrong model:
  ```
  Dimension mismatch: query uses 3072D (large) but index was built with 1536D (small).
  Use -m small or reindex with -m large.
  ```

### Technical

- 40 tests passing (up from 27)
- 13 new tests for embedding reuse feature
- Optimal default chunk size: 60 lines (tested for best relevance)

## [0.2.0] - 2026-01-10

### Added

- **Configurable Embedding Models**: Choose from multiple OpenAI embedding models:
  - `text-embedding-3-small` - Fast and affordable (default, $0.02/M tokens)
  - `text-embedding-3-large` - High accuracy for complex searches ($0.13/M tokens)
  - `text-embedding-ada-002` - Legacy compatibility ($0.10/M tokens)

- **Model Selection Options**:
  - CLI flag: `ogrep index . -m large`
  - Environment variable: `export OGREP_MODEL=large`
  - Model aliases: `small`, `large`, `ada`

- **New `ogrep models` Command**: View available embedding models with pricing and use cases

- **Short CLI Flags**:
  - `-m` for `--model`
  - `-d` for `--dimensions`
  - `-n` for `--top` (query results)
  - `-f` for `--force`

### Changed

- Restructured CLI into modular `ogrep/commands/` package
- Added comprehensive docstrings to all public modules
- Public Python API exports for library usage

### Technical

- 27 tests passing (up from 25)
- CLI complexity reduced from 38 to 11

## [0.1.0] - 2026-01-10

### Added

- **Semantic Code Search**: Search your codebase by meaning, not just keywords. Uses OpenAI embeddings with local SQLite storage for fast, private searches.

- **Full CLI Suite**: Complete command-line interface with `index`, `query`, `reset`, `reindex`, `clean`, and `status` commands.

- **Multi-Repo Scope Management**: Prevent cross-repo index pollution with flexible scope options:
  - `--db PATH` for custom database location
  - `--profile NAME` for named profiles
  - `--global-cache` for centralized caching
  - `--repo-root PATH` for explicit repository boundaries

- **Claude Code Integration**: Install directly from the Claude Code marketplace:
  ```
  /plugin marketplace add gplv2/ogrep-marketplace
  /plugin install ogrep@ogrep-marketplace
  ```

- Comprehensive test suite with 25 tests covering CLI, database, chunking, and end-to-end scenarios

- GitHub Actions CI workflow with Python 3.10, 3.11, 3.12 matrix testing

- Pre-commit hooks for code quality (ruff, yamllint)

- Developer documentation (CLAUDE.md, QUICKSTART.md)
