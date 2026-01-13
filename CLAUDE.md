# CLAUDE.md - Developer Guide for Claude Code

This file provides guidance for Claude Code when working in this repository.

## Repository Overview

**ogrep** is a local semantic grep tool with:
- SQLite-based local index (no external vector DB)
- OpenAI embeddings for semantic search (configurable model)
- Smart defaults for source-only indexing
- Auto-tuning for optimal chunk size
- Claude Code plugin/skill integration
- Multi-repo scope fencing

## Directory Structure

```
ogrep-marketplace/
├── .claude-plugin/           # Marketplace config
│   └── marketplace.json
├── ogrep/                    # Python package
│   ├── __init__.py           # Public API exports
│   ├── cli.py                # CLI argument parsing
│   ├── commands/             # CLI command implementations
│   │   ├── __init__.py
│   │   ├── _arg_builders.py  # Shared argument builders for CLI
│   │   ├── _common.py        # Shared utilities (scope resolution)
│   │   ├── chunk.py          # Chunk command (navigation)
│   │   ├── index.py          # Index command
│   │   ├── query.py          # Query command
│   │   ├── reset.py          # Reset command
│   │   ├── reindex.py        # Reindex command
│   │   ├── clean.py          # Clean command
│   │   ├── status.py         # Status command
│   │   ├── models.py         # Models command
│   │   ├── tune.py           # Tune command (auto-tuning)
│   │   └── benchmark.py      # Benchmark command (model comparison)
│   ├── models.py             # Embedding model definitions
│   ├── db.py                 # SQLite schema/connection
│   ├── indexer.py            # File indexing logic + DEFAULT_EXCLUDES
│   ├── search.py             # Query/search logic
│   ├── embed.py              # OpenAI embeddings
│   ├── chunking.py           # Text chunking
│   └── mcp/                  # MCP server (optional)
├── plugins/ogrep/            # Claude Code plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── commands/             # Slash commands
│   └── skills/               # Skills
├── tests/                    # Test suite
├── pyproject.toml            # Package config
├── .env.example              # Environment template
├── .pre-commit-config.yaml   # Pre-commit hooks
├── .yamllint.yaml            # YAML linting config
├── Makefile                  # Development commands
└── activate.sh               # Venv activation helper
```

## CLI Commands

All commands support `--json` for structured output (AI tool integration).

| Command | Description | JSON |
|---------|-------------|------|
| `ogrep index .` | Index a directory (source files only) | `--json` |
| `ogrep index . --list` | Preview files that would be indexed | `--json` |
| `ogrep query "text" -n 10 -r --json` | Semantic search (refresh, JSON) | `--json` |
| `ogrep query "text" --mode hybrid` | Hybrid search (semantic + keyword) | `--json` |
| `ogrep chunk "path:N" -C 1` | Get chunk by ref with context | `--json` |
| `ogrep status` | Show index stats | `--json` |
| `ogrep health` | Full database diagnostics | `--json` |
| `ogrep health --vacuum` | Reclaim space, defragment | `--json` |
| `ogrep health --rebuild-fts` | Rebuild FTS5 index | `--json` |
| `ogrep health --integrity` | Full integrity check | `--json` |
| `ogrep reset -f` | Delete index | `--json` |
| `ogrep reindex .` | Rebuild index (enables FTS5) | `--json` |
| `ogrep clean --vacuum` | Remove stale entries | `--json` |
| `ogrep models` | List available models | `--json` |
| `ogrep tune .` | Auto-tune chunk size | `--json` |
| `ogrep benchmark .` | Compare all models | `--json` |

### JSON Output Examples

```bash
# Index with JSON output
ogrep index . --json
# {"status":"success","files_indexed":42,"chunks_total":217,...}

# Status as JSON
ogrep status --json
# {"indexed":true,"files":42,"chunks":217,"model":"text-embedding-3-small",...}

# Clean with JSON
ogrep clean --json
# {"status":"success","removed_count":3,"removed_paths":[...],"vacuumed":false}

# Health as JSON
ogrep health --json
# {"tables":{...},"dedup_stats":{...},"fts5":{...},"sqlite_info":{...}}

# Models as JSON
ogrep models --json
# {"models":[{"id":"text-embedding-3-small","dimensions":1536,...}],...}
```

## AI Tool Integration (IMPORTANT)

### The --refresh Flag

**Always use `--refresh` (or `-r`) when querying from AI tools:**

```bash
ogrep query "where is auth handled" --refresh
```

The `--refresh` flag:
1. Checks all indexed files for changes (mtime/size comparison)
2. Runs incremental reindex on changed files (fast, reuses embeddings)
3. Then executes the query against fresh data

**Why this matters**: Without `--refresh`, queries may return stale results
based on outdated embeddings. This is especially critical in AI tool contexts
where files are being edited between queries.

### Search Modes

ogrep supports three search modes via `--mode` (or `-M`):

| Mode | Best For | Example |
|------|----------|---------|
| `semantic` | Conceptual questions | "where is authentication handled" |
| `fulltext` | Exact identifiers | "def validate_token" |
| `hybrid` | Mixed/unsure (default) | "authenticate user validation" |

```bash
ogrep query "authenticate" --mode semantic --json   # Embeddings only
ogrep query "def authenticate" --mode fulltext --json  # FTS5 keywords only
ogrep query "user login" --mode hybrid --json       # Combined (default)
```

**Default behavior:**
- Uses `OGREP_SEARCH_MODE` env var if set
- Falls back to `hybrid` if not set
- Gracefully degrades to `semantic` if FTS5 unavailable

### Chunk Navigation

After a query finds something interesting, use `ogrep chunk` to expand context:

```bash
ogrep chunk "src/auth.py:2"              # Get chunk by ref (from query results)
ogrep chunk "src/auth.py:2" --before 1   # + 1 chunk before
ogrep chunk "src/auth.py:2" --context 1  # + 1 before AND after
```

### Claude Code Hooks (Alternative)

Instead of using `--refresh` on every query, you can configure Claude Code
to automatically reindex after file edits using hooks.

#### Hook Configuration

Create or edit `.claude/settings.json` in your project root:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "ogrep index . 2>/dev/null || true"
      }
    ]
  }
}
```

#### Hook File Locations

| Location | Scope | Path |
|----------|-------|------|
| **Project** | This repo only | `<repo>/.claude/settings.json` |
| **User** | All repos | `~/.claude/settings.json` |

#### Example: Full Hook Configuration

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "ogrep index . 2>/dev/null || true"
      }
    ]
  }
}
```

**Matcher options:**
- `"Edit|Write"` - Trigger on file edits and writes
- `"Edit"` - Only on Edit tool
- `".*"` - All tool uses (not recommended)

### When to Use Each Approach

| Approach | Best For | Trade-offs |
|----------|----------|------------|
| `--refresh` flag | General use, any environment | Small latency on each query |
| Claude Code hooks | Heavy editing sessions | Requires Claude Code, config setup |
| Both | Maximum reliability | Redundant but safe |

**Recommendation**: The semantic-grep skill uses `--refresh` by default.
Add hooks as an optimization if query latency becomes noticeable during
heavy editing sessions.

## Smart Defaults

### Source-Only Indexing

Defined in `ogrep/indexer.py` as `DEFAULT_EXCLUDES`:

| Category | Patterns |
|----------|----------|
| **Binary** | `*.pyc`, `*.so`, `*.dll`, `*.exe`, `*.whl` |
| **Secrets** | `.env`, `.env.*`, `secrets.*`, `credentials.*` |
| **Docs** | `*.md`, `*.txt`, `*.rst`, `docs/*` |
| **Config** | `*.json`, `*.toml`, `*.ini`, `.editorconfig` |
| **Build** | `dist/*`, `build/*`, `vendor/*`, `target/*` |
| **Lock files** | `*.lock`, `package-lock.json`, `yarn.lock`, `poetry.lock` |
| **Git metadata** | `.gitignore`, `.gitattributes`, `.gitmodules`, `.gitkeep` |
| **Images** | `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.webp`, `*.ico`, `*.bmp`, `*.tiff`, `*.psd` |
| **Fonts** | `*.woff`, `*.woff2`, `*.ttf`, `*.otf`, `*.eot` |
| **Media** | `*.mp3`, `*.mp4`, `*.wav`, `*.avi`, `*.mov`, `*.webm` |
| **Archives** | `*.zip`, `*.tar`, `*.gz`, `*.rar`, `*.7z` |
| **Databases** | `*.sqlite`, `*.sqlite3`, `*.db`, `*.sql`, `*.dump` |
| **Logs/temp** | `*.log`, `logs/*`, `*.tmp`, `*.temp` |
| **Backups** | `*.old`, `*.bak`, `*.backup`, `*.orig`, `*.swp`, `*~` |
| **Data files** | `*.csv`, `*.tsv`, `*.sqlt`, `*.dat`, `*.xml` |
| **Python packages** | `*.dist-info/*`, `*.egg-info/*`, `*.pth`, `py.typed` |

**Note:** YAML files (`*.yaml`, `*.yml`) are now **indexed by default** (v0.6.3+) to support searching CI/CD pipelines, Kubernetes manifests, and other configuration.

**Skipped directories** (in `DEFAULT_SKIP_DIRS`):
- `.git`, `.svn`, `.hg` (version control)
- `.venv`, `venv`, `node_modules` (dependencies)
- `__pycache__`, `.ogrep` (caches)
- `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.tox` (tool caches)
- `.githooks`, `storage` (misc)

**Additional filtering:**
- Empty files (0 bytes) are skipped
- Duplicate symlinks (pointing to same real path) are skipped
- Broken symlinks are skipped

### Chunk Size Optimization

Default: **60 lines** with 10-line overlap.

Tested results:

| Chunk Size | Accuracy | Notes |
|------------|----------|-------|
| 30 lines | 0.64 | Too granular |
| 45 lines | 0.88 | Good |
| **60 lines** | **0.92** | **Best (default)** |
| 90 lines | 0.92 | Equivalent |
| 120 lines | 0.92 | Larger context |

### Smart Embedding Reuse

Implemented in `ogrep/indexer.py` - minimizes API token usage:

1. **File unchanged**: Completely skipped (mtime, size, sha256 match)
2. **File modified**: Cache existing chunk embeddings by `text_sha256` before delete
3. **Re-chunk**: Compute new chunk hashes
4. **Reuse**: Match new hashes against cached embeddings
5. **Embed**: Only call API for truly new chunks

**Key code path:**
```python
# Cache existing embeddings before deletion
existing_embeddings = {r[0]: (r[1], r[2]) for r in
    con.execute("SELECT text_sha256, embedding, dim FROM chunks WHERE file_id=?")}

# After re-chunking, check each chunk's hash
if tsha in existing_embeddings:
    reusable_indices.append((i, existing_embeddings[tsha]))
else:
    chunks_to_embed.append((i, text))
```

**`IndexStats` dataclass** tracks: `files_scanned`, `files_indexed`, `files_skipped`, `chunks_total`, `chunks_reused`, `chunks_reused_global`, `chunks_reused_local`, `chunks_embedded`, `tokens_saved_estimate`, `dedup_ratio`.

### Cross-File Chunk Deduplication

Beyond single-file reuse, ogrep now deduplicates identical chunks **across different files**. This is especially valuable for:

- Legacy codebases with copied/forked files
- Template-based code generation
- Vendored dependencies with minor customizations

**How it works:**

1. **Global lookup**: Before embedding, query ALL existing chunks by `text_sha256`
2. **Integrity checks**: Verify model and dimension match before reusing
3. **Priority**: Global reuse > Local reuse > New embedding

**Example savings:**

| Scenario | Before | After | Savings |
|----------|--------|-------|---------|
| Two 1000-line files, 10 lines different | 132 embeddings | 68 embeddings | 49% |
| 5 copies of same 500-line file | 165 embeddings | 33 embeddings | 80% |

**Database index** (`idx_chunks_text_sha256`) enables O(log n) cross-file lookups.

**Model consistency check**: Prevents mixing different embedding models in the same index. If you try to index with a different model, you'll get:
```
ValueError: Model mismatch: index uses 'nomic-embed-text-v1.5' but requested 'text-embedding-3-small'. Use --force to reindex with new model.
```

**Stats tracking:**
- `chunks_reused_global`: Count of chunks reused from OTHER files
- `chunks_reused_local`: Count of chunks reused from SAME file (edits)
- `dedup_ratio`: Percentage of chunks that were deduplicated

## File Filtering Flags

| Flag | Description |
|------|-------------|
| `-e`, `--exclude PATTERN` | Add patterns to exclude |
| `-i`, `--include PATTERN` | Override default excludes |
| `-l`, `--list` | Preview files with detection (dry run) |
| `--no-detect` | Disable MIME detection (fast null-byte only) |

Examples:
```bash
ogrep index . -e 'test_*'      # Exclude test files
ogrep index . -i '*.md'        # Include markdown (normally excluded)
ogrep index . --list           # Preview with file type detection
ogrep index . --no-detect      # Skip MIME detection (faster)
```

### File Type Detection

By default, ogrep uses the `file` command for accurate MIME type detection. This catches:
- Binary files without extensions (SQLite databases, etc.)
- Files with misleading extensions
- Data files that pass simple null-byte checks

Use `--no-detect` to disable MIME detection and use only the fast null-byte check.

### Previewing Files with --list

Use `--list` to see what files would be indexed, with detection results:

```bash
ogrep index . --list
```

Output shows files sorted by extension, with binary files marked:

```
── .py (34 files, 179.6KB) ──
       24B  tests/__init__.py
      101B  ogrep/__main__.py
    17.0KB  ogrep/commands/benchmark.py

── (no extension) (3 files, 45.2KB) ──
  [BINARY: application/x-sqlite3]   12.0KB  data
      25.2KB  Makefile

──────────────────────────────────────────────────
Would index: 35 files, 180.4KB
Excluded by detection: 1 files, 12.0KB

Largest indexable:
    17.0KB  ogrep/commands/benchmark.py

Largest excluded (binary):
   12.0KB  data (application/x-sqlite3)
```

This helps identify:
- Binary files that would be excluded
- Large data files slowing down indexing
- Files to add to `.ogrepignore`

## .ogrepignore File

Create a `.ogrepignore` file in your repo root to permanently exclude patterns without passing `-e` every time.

### Syntax

```
# Comments start with #
# Empty lines are ignored

# Glob patterns (same as -e flag)
*.sql
*.generated.ts
migrations/*

# Directory patterns
legacy/*
experiments/*
```

### Example .ogrepignore

```
# Database dumps and migrations
*.sql
migrations/*

# Generated code
*.generated.ts
*.generated.go
codegen/*

# Legacy code (not worth indexing)
legacy/*

# Large vendor files
third_party/*
```

### Precedence

1. **DEFAULT_EXCLUDES** (built-in patterns in `indexer.py`)
2. **`.ogrepignore`** (repo-specific patterns)
3. **`-e` / `--exclude`** (command-line patterns)
4. **`-i` / `--include`** (overrides all excludes)

All exclude sources are combined. Use `--include` to override any exclusion.

## Auto-Tuning

The `tune` command tests different chunk sizes:

```bash
ogrep tune .           # Test and recommend
ogrep tune . --apply   # Test and reindex with optimal settings
ogrep tune . -s 10     # Use 10 test samples
```

**How it works:**
1. Scans for significant patterns (function/class definitions)
2. Creates semantic queries ("where is function X defined")
3. Tests chunk sizes: 30, 45, 60, 90, 120
4. Measures if correct file+line appears in top 5 results
5. Reports accuracy and recommends optimal chunk size

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Required for OpenAI models | - |
| `OGREP_MODEL` | Default embedding model | Smart default* |
| `OGREP_DIMENSIONS` | Default dimensions | Model default |
| `OGREP_CHUNK_LINES` | Chunk size from tuning (overrides model default) | Model-specific |
| `OGREP_BATCH_SIZE` | Batch size for embedding requests | Auto-tuned** |
| `OGREP_BASE_URL` | Local server URL (e.g., LM Studio) | - |
| `OGREP_SEARCH_MODE` | Default search mode (semantic, fulltext, hybrid) | `hybrid` |
| `OGREP_FUSION_METHOD` | Hybrid fusion method (`rrf` or `alpha`) | `rrf` |
| `OGREP_RRF_K` | RRF rank constant (higher = smoother ranking) | `60` |
| `OGREP_HYBRID_ALPHA` | Alpha fusion: semantic weight (0.0-1.0) | `0.7` |
| `OGREP_RERANK_MODEL` | Cross-encoder model for reranking | `BAAI/bge-reranker-v2-m3` |
| `OGREP_RERANK_TOPN` | Default candidates to rerank | `50` |
| `OGREP_CONFIDENCE_MODE` | Confidence scoring mode: `relative` or `absolute` | `relative` |
| `OGREP_RELATIVE_HIGH` | Relative mode: fraction of top score for "high" | `0.90` |
| `OGREP_RELATIVE_MEDIUM` | Relative mode: fraction of top score for "medium" | `0.75` |
| `OGREP_RELATIVE_LOW` | Relative mode: fraction of top score for "low" | `0.50` |
| `OGREP_CONFIDENCE_HIGH` | Absolute mode: threshold for "high" | `0.50` |
| `OGREP_CONFIDENCE_MEDIUM` | Absolute mode: threshold for "medium" | `0.40` |
| `OGREP_CONFIDENCE_LOW` | Absolute mode: threshold for "low" | `0.30` |
| `OGREP_INTEGRATION_TESTS` | Enable real API tests | - |

**Smart Model Default:**
- If `OGREP_BASE_URL` is set → `nomic` (local model, best balance)
- Otherwise → `text-embedding-3-small` (OpenAI)

**Batch Size Auto-Tuning:**
- Local models: default 16, max varies by model (16-32)
- OpenAI models: default 200, max 2048
- Auto-tuning tests multiple batch sizes and picks fastest
- Manual override via `OGREP_BATCH_SIZE` (capped to model's max)

## Understanding Confidence Scores

### Why Scores Look "Low" (But Search Works Fine)

Cosine similarity for text embeddings does NOT distribute uniformly across [0, 1]. Instead, scores cluster around 0.3-0.5:

```
Distribution of pairwise similarities in a typical codebase:
├── 0.0-0.2  ████████░░░░░░░░░░░░  ~15%
├── 0.2-0.3  ████████████░░░░░░░░  ~30%
├── 0.3-0.4  ████████████████░░░░  ~35%  ← MEDIAN IS HERE
├── 0.4-0.5  ██████░░░░░░░░░░░░░░  ~12%
├── 0.5-0.6  ███░░░░░░░░░░░░░░░░░  ~5%
├── 0.6-0.7  █░░░░░░░░░░░░░░░░░░░  ~2%
└── 0.7+     ░░░░░░░░░░░░░░░░░░░░  ~1% (near-duplicates only)
```

**What this means for search:**
- A score of 0.40 is in the **top 20%** of all possible matches
- A score of 0.50 is in the **top 10%** of all possible matches
- A score of 0.60 is in the **top 2%** of all possible matches
- Getting above 0.70 requires near-duplicate text

### Relative vs Absolute Confidence

**Relative mode (default)** compares each result to the top score:

| Top Score | Result Score | Ratio | Confidence |
|-----------|--------------|-------|------------|
| 0.45 | 0.45 | 100% | high |
| 0.45 | 0.42 | 93% | high |
| 0.45 | 0.35 | 78% | medium |
| 0.45 | 0.20 | 44% | very_low |

This is more meaningful because it tells you how close each result is to the best match, regardless of absolute scores.

**Absolute mode** uses fixed thresholds. Useful if you've calibrated for your specific codebase:

```bash
# Switch to absolute mode with custom thresholds
export OGREP_CONFIDENCE_MODE=absolute
export OGREP_CONFIDENCE_HIGH=0.50
export OGREP_CONFIDENCE_MEDIUM=0.40
export OGREP_CONFIDENCE_LOW=0.30
```

### Tuning for Legacy/Sparse Codebases

For legacy code with sparse comments, consider:

```bash
# Hybrid fusion uses RRF (Reciprocal Rank Fusion) by default (v0.7.0+)
# RRF combines by rank position, not scores - more robust

# To switch to alpha weighting (legacy):
export OGREP_FUSION_METHOD=alpha
export OGREP_HYBRID_ALPHA=0.4  # More keyword-heavy

# Or use fulltext mode for exact identifier searches
ogrep query "validateToken" --mode fulltext
```

## Embedding Models

### OpenAI Models (Cloud)

| Model | Alias | Dimensions | Use Case |
|-------|-------|------------|----------|
| text-embedding-3-small | `small` | 1536 | Default, cost-effective |
| text-embedding-3-large | `large` | 3072 | High accuracy |
| text-embedding-ada-002 | `ada` | 1536 | Legacy |

### Local Models (via LM Studio)

| Model | Alias | Dimensions | Context | Max Batch | Optimal Chunk | Accuracy |
|-------|-------|------------|---------|-----------|---------------|----------|
| nomic-embed-text-v1.5 | `nomic` | 768 | 8192 | 32 | 30 lines | 72% |
| all-MiniLM-L6-v2 | `minilm` | 384 | 256 | 16 | 30 lines | 96% |
| bge-base-en-v1.5 | `bge` | 768 | 512 | 16 | 30 lines | 52% |
| bge-m3 | `bge-m3` | 1024 | 8192 | 32 | 60 lines | TBD |

**Smart Default:** When `OGREP_BASE_URL` is set, ogrep auto-selects `nomic` (best balance of accuracy and context).

**Important:** Query model must match index model.

### Batch Size Limits

Each model has a `max_batch_size` to prevent context overflow:

| Model Type | Default | Max | Auto-Tune Steps |
|------------|---------|-----|-----------------|
| Local (minilm, bge) | 16 | 16 | 8, 16 |
| Local (nomic, bge-m3) | 16 | 32 | 8, 16, 32 |
| OpenAI (all) | 200 | 2048 | 64, 128, 256, 512, 768, 1024, 2048 |

OpenAI benefits greatly from larger batches (38x faster at batch 200 vs serial).

### Model Context Limits

Each model has a maximum context window (in tokens):

| Model | Context Tokens | Chars/Token (est.) | Max Text per Chunk |
|-------|----------------|--------------------|--------------------|
| minilm | 256 | ~3 | ~768 chars |
| bge | 512 | ~3 | ~1,536 chars |
| nomic | 8,192 | ~3 | ~24,576 chars |
| bge-m3 | 8,192 | ~3 | ~24,576 chars |
| OpenAI (all) | 8,191 | ~4 | ~32,764 chars |

**Token estimation**: ogrep uses ~3 chars/token for code (conservative). If a chunk exceeds the limit, it's automatically truncated with a warning.

**Auto-retry**: If the API still returns a context overflow, ogrep parses the error, truncates further, and retries (up to 3x).

### Token-Aware Batching with Auto-Retry

Batches are automatically split to respect model context limits:

- **Token estimation**: ~3 chars per token for code (conservative baseline)
- **Safety margin**: 10% under the limit to account for estimation variance
- **Oversized chunks**: Single chunks exceeding context are truncated with a warning
- **Auto-retry**: If API returns context overflow, parses error, truncates further, retries (up to 3x)
- **No configuration needed**: Works automatically for all models

**Token limits by model:**

| Model | Context Tokens | Max Batch Size |
|-------|----------------|----------------|
| OpenAI (all) | 8,191 | 2,048 |
| nomic | 8,192 | 32 |
| bge-m3 | 8,192 | 32 |
| minilm | 256 | 16 |
| bge | 512 | 16 |

**Example warnings:**

```
# Upfront estimation catches most overflows
Text truncated from ~10304 tokens to ~7371 tokens to fit context window

# If estimation is off, auto-retry kicks in
Context overflow (9047 > 8192 tokens). Truncating to 77% and retrying...
```

This prevents crashes on large codebases with very long functions or dense code.

## Local Embedding Models

Use local embedding models for offline operation, privacy, or cost-free usage.

### Prerequisites

#### Step 1: Install LM Studio

**System Requirements:**
- 16GB RAM minimum (for embedding models)
- macOS 13.6+, Windows 10+, or Ubuntu 22.04+

Download LM Studio from [lmstudio.ai](https://lmstudio.ai/):

**macOS:**
1. Download the DMG from [lmstudio.ai](https://lmstudio.ai/)
2. Open the DMG and drag LM Studio to Applications
3. **Launch LM Studio once** - this creates `~/.lmstudio/` directory

**Linux (Ubuntu/Debian):**
1. Download the AppImage from [lmstudio.ai](https://lmstudio.ai/)
2. Make executable: `chmod +x LM-Studio-*.AppImage`
3. **Run it once**: `./LM-Studio-*.AppImage` - this creates `~/.lmstudio/` directory
4. Close LM Studio after it finishes initializing

**Windows:**
1. Download the installer from [lmstudio.ai](https://lmstudio.ai/)
2. Run the EXE installer
3. **Launch LM Studio once** - this creates the `.lmstudio` directory

> **Important:** You must launch LM Studio at least once before proceeding.
> The CLI is only available after LM Studio creates the `~/.lmstudio/` directory.

#### Step 2: Add CLI to PATH

After LM Studio has been launched once, add the `lms` CLI to your PATH:

**macOS/Linux:**
```bash
~/.lmstudio/bin/lms bootstrap
lms --version  # Verify: should show version number
```

**Windows (PowerShell):**
```powershell
& "$env:USERPROFILE\.lmstudio\bin\lms.exe" bootstrap
lms --version
```

**Troubleshooting:** If you get "command not found" or "directory not found":
- Ensure LM Studio was launched at least once
- Check that `~/.lmstudio/bin/lms` exists: `ls ~/.lmstudio/bin/`
- If using a custom install location, check `~/.lmstudio-home-pointer`:
  ```bash
  cat ~/.lmstudio-home-pointer  # Shows actual LM Studio home
  # Then use that path, e.g.:
  ~/.cache/lm-studio/bin/lms bootstrap
  ```
- If missing, launch LM Studio again and wait for it to fully initialize

### Setup

1. **Download an embedding model:**
   ```bash
   # Download nomic (recommended - good balance of speed and quality)
   lms get nomic-embed-text-v1.5 -y

   # Or download BGE (higher quality quantization)
   lms get bge-base-en-v1.5 -y

   # List downloaded models
   lms ls
   ```

2. **Load the model into memory:**
   ```bash
   # Load nomic
   lms load nomic-ai/nomic-embed-text-v1.5-GGUF -y

   # Or load BGE
   lms load bge-base-en-v1.5 -y
   ```

3. **Start the server:**
   ```bash
   lms server start --port 1234
   lms server status  # Verify: "Server: ON (port: 1234)"
   ```

4. **Configure ogrep:**
   ```bash
   export OGREP_BASE_URL=http://localhost:1234/v1
   ```

### Usage

```bash
# Index with local model
ogrep index . -m nomic

# Query with local model
ogrep query "where is auth handled" -m nomic -r

# Check status
ogrep status
```

### Using .env File

```bash
# .env
OGREP_BASE_URL=http://localhost:1234/v1
OGREP_MODEL=nomic-embed-text-v1.5
```

### Chunk Size and Overlap Tuning

**Critical:** Different models require different chunk sizes and overlap for optimal results.

| Model | Optimal Chunk | Optimal Overlap | Notes |
|-------|---------------|-----------------|-------|
| minilm | 30 lines | 5 lines | Best accuracy (96%), small chunks |
| nomic | 30 lines | 15 lines | Large context window (8192 tokens) benefits from more overlap |
| bge | 30 lines | 10 lines | Fails at 90+ lines |
| bge-m3 | 60 lines | 10 lines | Multi-lingual support |

**Benchmark to find optimal settings for your codebase:**

```bash
# Comprehensive benchmark of all available models
ogrep benchmark . --samples 10

# Save optimal settings to .env
ogrep benchmark . --samples 10 --save

# Or use tune for a specific model
ogrep tune . -m nomic -s 10 --save --apply
```

### Dimension Mismatch

OpenAI models use 1536D or 3072D, local models use 768D. You cannot mix models:

```
Dimension mismatch: query uses 768D (nomic) but index was built with 1536D (small).
Use -m small or reindex with -m nomic.
```

### Corrupted Index (Mixed Dimensions)

If you see this error, your index has embeddings from multiple models:

```
ValueError: Corrupted index: mixed dimensions detected ([768, 1536]).
This can happen if --refresh was run with a different model.
Run 'ogrep reset -f && ogrep index .' to rebuild.
```

**Fix:** Rebuild from scratch:
```bash
ogrep reset -f && ogrep index .
```

This can happen if `--refresh` was used with a different model before the bug fix in v0.5.1+.

### Auto-Start Server on Boot

Configure LM Studio settings to start the server on login without GUI.

### Detailed Tuning Guide

For comprehensive benchmarks, model comparisons, and troubleshooting, see:
[LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md)

## Development Workflow

### Setup

```bash
source .venv/bin/activate
pip install -e ".[dev]"
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
| `ogrep/cli.py` | CLI argument parsing and dispatch |
| `ogrep/commands/` | Individual command implementations |
| `ogrep/models.py` | Embedding model definitions and resolution |
| `ogrep/indexer.py` | File walking, filtering, indexing logic |
| `ogrep/search.py` | Query execution and scoring |
| `ogrep/db.py` | SQLite schema and connection |
| `tests/conftest.py` | Pytest fixtures with OpenAI mock |

## Common Tasks

### Adding a new CLI command

1. Create `ogrep/commands/<name>.py` with `cmd_<name>` function
2. Export from `ogrep/commands/__init__.py`
3. Add parser in `cli.py` `_build_parser()` function
4. Add tests in `tests/test_cli.py`
5. Add command file in `plugins/ogrep/commands/<name>.md`

### Modifying default excludes

1. Edit `DEFAULT_EXCLUDES` tuple in `ogrep/indexer.py`
2. Run tests to ensure nothing breaks
3. Update documentation

### Adding a new embedding model

1. Add entry to `MODELS` dict in `models.py`
2. Optionally add alias to `MODEL_ALIASES`
3. Update documentation

### Adding a new skill

1. Create `plugins/ogrep/skills/<name>/SKILL.md`
2. Define frontmatter with `name`, `description`, `allowed-tools`
3. Document skill behavior in markdown body

### Bumping version

Update ALL these files when releasing a new version:

| File | Field |
|------|-------|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `ogrep/__init__.py` | `__version__ = "X.Y.Z"` |
| `ogrep/cli.py` | `__version__ = "X.Y.Z"` |
| `.claude-plugin/marketplace.json` | `"version": "X.Y.Z"` (top-level only) |
| `plugins/ogrep/.claude-plugin/plugin.json` | `"version": "X.Y.Z"` |
| `tests/test_cli.py` | Version assertion (search for old version) |
| `LOCAL_EMBEDDINGS_GUIDE.md` | Environment section `**ogrep:**` |

#### CRITICAL: Marketplace JSON Structure

**DO NOT modify the structure of these files. Only change version numbers and descriptions.**

The marketplace breaks if you add fields like `version`, `author`, `category`, `tags` **inside `plugins[]`** array.
Fields at the top level and in plugin.json are fine.

**`.claude-plugin/marketplace.json` - EXACT working structure:**
```json
{
  "name": "ogrep-marketplace",
  "version": "X.Y.Z",
  "description": "Claude Code marketplace for ogrep - semantic code search with multiple modes: semantic (conceptual), fulltext (FTS5), and hybrid. Supports local models via LM Studio (offline, free) or OpenAI embeddings.",
  "owner": {
    "name": "gplv2",
    "email": "glenn@bitless.be",
    "url": "https://github.com/gplv2"
  },
  "plugins": [
    {
      "name": "ogrep",
      "source": "./plugins/ogrep",
      "description": "Semantic code search with multiple modes: semantic (embedding similarity for conceptual queries), fulltext (FTS5 keyword matching for exact identifiers), and hybrid (combined - best of both). JSON output for AI tools."
    }
  ]
}
```

**NOTE:** Inside `plugins[]`, only `name`, `source`, and `description` are allowed.
Do NOT add `version`, `author`, or `category` inside the plugins array - it breaks the marketplace.

**`plugins/ogrep/.claude-plugin/plugin.json` - EXACT working structure:**
```json
{
  "name": "ogrep",
  "version": "X.Y.Z",
  "description": "Semantic code search with multiple modes: semantic (embedding similarity for conceptual queries), fulltext (FTS5 keyword matching for exact identifiers), and hybrid (combined - best of both). Supports local models via LM Studio (offline, free) or OpenAI embeddings. JSON output for AI tools.",
  "author": {
    "name": "gplv2",
    "email": "glenn@bitless.be"
  },
  "skills": "./skills/",
  "commands": ["./commands/"]
}
```

**Verification command:**
```bash
grep -rn "X\.Y\.Z\|OLD_VERSION" --include="*.py" --include="*.json" --include="*.toml" --include="*.md" | grep -v CHANGELOG | grep -v RELEASE_NOTES
```

**After updating:**
1. Commit changes
2. Create annotated tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z - description"`
3. Push: `git push && git push --tags`

## Debugging Tips

```bash
# Check index status
ogrep status

# Full database diagnostics (includes dedup stats)
ogrep health

# Reset and reindex
ogrep reindex .

# View database directly
sqlite3 .ogrep/index.sqlite

# Check for stale files
ogrep clean --vacuum

# List models
ogrep models

# Test chunk sizes
ogrep tune . -s 5
```

### Health Command Output

The `ogrep health` command shows comprehensive diagnostics:

```
── Tables ──
  chunks          217 rows      1.7 MB
  files            41 rows      8.0 KB

── Dedup Stats ──
  Total chunks: 11
  Unique hashes: 5
  Deduplicated: 6 (54.5% embedding savings)

── FTS5 Stats ──
  Rows indexed: 217
  Tokens (est): 54,073

── Embedding Model ──
  Model: text-embedding-3-small
  Dimensions: 1536
```

**Dedup Stats** shows cross-file chunk deduplication:
- **Total chunks**: All chunks in the index
- **Unique hashes**: Distinct `text_sha256` values
- **Deduplicated**: Chunks sharing embeddings with others (savings percentage)

## Plugin Structure

The Claude Code plugin is at `plugins/ogrep/`:

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

## Scope Fencing

Prevents cross-repo pollution:

1. **Default**: `.ogrep/index.sqlite` in repo root
2. **Profile**: `.ogrep/<profile>/index.sqlite`
3. **Global cache**: `~/.cache/ogrep/<hash>/index.sqlite`
4. **Explicit**: `--db /path/to/db.sqlite`

## Testing Notes

- Tests use a mock OpenAI client by default (see `conftest.py`)
- Real API tests are marked with `@pytest.mark.integration`
- Run integration tests with: `OGREP_INTEGRATION_TESTS=1 pytest -m integration`

### Test Files

| File | Coverage |
|------|----------|
| `tests/test_chunking.py` | Text chunking logic |
| `tests/test_chunk_command.py` | Chunk navigation command |
| `tests/test_cli.py` | CLI help and argument parsing |
| `tests/test_db.py` | Database schema and connections |
| `tests/test_roundtrip.py` | End-to-end index/query flow |
| `tests/test_embedding_reuse.py` | Smart embedding reuse (13 tests) |
| `tests/test_benchmark.py` | Benchmark command (21 tests) |
| `tests/test_models.py` | Model resolution and configuration |
| `tests/test_query_command.py` | Query command (JSON output, etc.) |
| `tests/test_search.py` | Query execution and scoring |

### Key Embedding Reuse Tests

- `test_embedding_reuse_on_small_edit`: Verifies unchanged chunks reuse embeddings
- `test_embedding_reuse_append_only`: Tests common append-only edit pattern
- `test_embedding_preserved_in_db`: Confirms reused embeddings are byte-identical
- `test_tokens_saved_estimate`: Validates savings calculation
