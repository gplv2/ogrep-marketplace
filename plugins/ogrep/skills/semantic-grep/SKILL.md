---
name: semantic-grep
description: |
  Semantic code search with multiple modes: semantic (embedding similarity), fulltext (FTS5 keywords), and hybrid (combined - best of both). Proactively use when:
  - User asks WHERE something is implemented ("where is X handled", "how does Y work")
  - User needs to understand code behavior vs finding exact names
  - Exact grep would require knowing the right terms first
  - User wants to search codebase by meaning, not just keywords
  Use when appropriate context detected. Trigger with conceptual code questions.
allowed-tools: Bash, Read
---

# Semantic grep workflow (ogrep) v0.6.4

Fast semantic search over local repos using `ogrep` (SQLite index + embeddings).

## Quick Examples (Copy & Paste)

```bash
# Search by concept (semantic)
ogrep query "where is authentication handled" -n 10 --refresh --json

# Search by exact identifier (fulltext)
ogrep query "def validate_token" --mode fulltext --json

# Combined search (hybrid - default)
ogrep query "user login validation" -n 15 --refresh --json

# Expand context around a result
ogrep chunk "src/auth.py:2" --context 1 --json

# Index the repo (first time or after major changes)
ogrep index .

# Check index status
ogrep status --json
```

## Common Patterns

| Task | Command |
|------|---------|
| Find where X is implemented | `ogrep query "where is X handled" --json` |
| Find exact function/class | `ogrep query "def function_name" --mode fulltext --json` |
| Understand how X works | `ogrep query "how does X work" -n 15 --json` |
| Find all uses of X | `ogrep query "X" --mode fulltext --json` |
| Search after editing files | `ogrep query "..." --refresh --json` |
| Get more context | `ogrep chunk "file.py:N" --context 2` |
| Find config/YAML | `ogrep query "database configuration" --json` |
| Find error handling | `ogrep query "exception handling" --json` |

## Key Features

- **Three search modes**: semantic (conceptual), fulltext (exact), hybrid (combined)
- **Relative confidence scoring**: Compares results to top match (v0.6.4+)
- **JSON output for all commands**: Structured data for AI tool integration
- **Chunk navigation**: Expand context around search results
- **Smart embedding reuse**: Minimal API costs on reindex
- **YAML files indexed**: Configuration files now searchable by default

## Quick Start

```bash
# Index the repo (run once, or after major changes)
ogrep index .

# Semantic search with JSON output (recommended for AI tools)
ogrep query "where is authentication handled?" -n 15 --json

# Use --refresh to ensure freshness after recent edits
ogrep query "database connection logic" -n 10 --refresh --json
```

### When to Use --refresh

The `--refresh` flag checks for changed files and reindexes them before searching:

- **Use --refresh**: After editing files, or when you need guaranteed fresh results
- **Skip --refresh**: For faster queries when you know files haven't changed recently

The refresh operation is fast due to smart embedding reuse (unchanged chunks keep their embeddings).

## Search Modes

ogrep supports three search modes via `--mode` (or `-M`):

| Mode | Best For | Example Query |
|------|----------|---------------|
| `semantic` | Conceptual questions | "where is user authentication handled" |
| `fulltext` | Exact identifiers | "def validate_token" |
| `hybrid` | Mixed/unsure (default) | "authenticate user validation" |

```bash
# Explicit mode selection
ogrep query "authenticate" --mode semantic --json   # Embeddings only
ogrep query "def authenticate" --mode fulltext --json  # Keywords only
ogrep query "user login" --mode hybrid --json       # Combined (default)
```

**Default behavior:**
- Uses `OGREP_SEARCH_MODE` env var if set
- Falls back to `hybrid` if not set
- Gracefully degrades to `semantic` if FTS5 unavailable

### When to Use Each Mode

| Situation | Mode | Why |
|-----------|------|-----|
| "How does X work?" | semantic | Conceptual understanding |
| "Where is X implemented?" | semantic/hybrid | Need related code, not exact match |
| Looking for exact function name | fulltext | Know the identifier |
| Found semantic result, want exact matches | fulltext | Refine initial finding |
| Unsure what terms codebase uses | hybrid | Best of both worlds |

## Chunk Navigation

After a query finds something interesting, use `ogrep chunk` to expand context:

```bash
# Get chunk by reference (from query results)
ogrep chunk "src/auth.py:2"

# Get surrounding context
ogrep chunk "src/auth.py:2" --before 1    # + 1 chunk before
ogrep chunk "src/auth.py:2" --after 1     # + 1 chunk after
ogrep chunk "src/auth.py:2" --context 1   # + 1 before AND after

# Also works with raw chunk IDs
ogrep chunk 42
```

### Direct Chunk Access

You can access chunks directly without querying first:

```bash
# Access chunk 0 (first chunk) of any file
ogrep chunk "src/main.py:0" --json

# Access specific chunk by file path and index
ogrep chunk "src/models/user.py:3" --json

# Access by database chunk ID (from previous query results)
ogrep chunk 42 --json
ogrep chunk 157 --context 1 --json
```

**Understanding chunk_ref format:** `"path/to/file.py:N"` where N is the chunk index (0-based) within that file. Each chunk is ~60 lines of code by default.

### Navigating Neighbors

Neighbors are chunks adjacent to your target - use them to understand context:

```bash
# See what comes BEFORE the target chunk
ogrep chunk "handler.py:5" --before 2 --json
# Returns: requested chunk + 2 chunks before it

# See what comes AFTER the target chunk
ogrep chunk "handler.py:5" --after 2 --json
# Returns: requested chunk + 2 chunks after it

# See BOTH directions (full context)
ogrep chunk "handler.py:5" --context 2 --json
# Returns: 2 before + target + 2 after (5 total chunks)
```

**When to expand neighbors:**
| Situation | Direction | Example |
|-----------|-----------|---------|
| Found function body, need signature | `--before 1` | Class definition above |
| Found function, need to see caller | `--after 1` | What happens next |
| Found config, need full section | `--context 1` | Surrounding settings |
| Debugging flow, need full picture | `--context 2` | Bigger context |

### Chunk Navigation Patterns

#### Pattern 1: Expand Context After Query
```bash
# Query found something in chunk 3, want to see setup above
ogrep query "database connection" --json
# Result: chunk_ref: "db.py:3"
ogrep chunk "db.py:3" --before 1
```

#### Pattern 2: Trace Function Flow
```bash
# Found a function, want to see what comes next
ogrep chunk "handler.py:2" --after 2
```

#### Pattern 3: Understand Full Module Section
```bash
# Found interesting code, want full surrounding context
ogrep chunk "auth.py:4" --context 2
```

#### Pattern 4: Quick Keyword Lookup
```bash
# Know exact function name
ogrep query "def process_request" --mode fulltext --json
```

#### Pattern 5: Walk Through a File Sequentially
```bash
# Start at the beginning of a file
ogrep chunk "api/routes.py:0" --json
# Then walk forward
ogrep chunk "api/routes.py:1" --json
ogrep chunk "api/routes.py:2" --json
# Or get multiple at once
ogrep chunk "api/routes.py:0" --after 3 --json
```

#### Pattern 6: Find Class Definition from Method
```bash
# Query found a method in chunk 5
ogrep query "def validate_credentials" --json
# Result: chunk_ref: "auth/user.py:5"
# Look backward to find the class definition
ogrep chunk "auth/user.py:5" --before 2 --json
```

## Confidence Levels

Each result includes a `confidence` level using **relative scoring** (v0.6.4+). Confidence compares each result to the top score, not fixed thresholds:

| Confidence | Relative Score | What It Means |
|------------|----------------|---------------|
| `high` | 90%+ of top | Trust and use directly |
| `medium` | 75-89% of top | Use but verify with context |
| `low` | 50-74% of top | Consider alternative queries |
| `very_low` | < 50% of top | Likely not relevant |

**Why relative scoring matters:**
Cosine similarity scores cluster around 0.3-0.5 (not uniformly [0,1]). A score of 0.45 is excellent! Relative scoring answers: "How good is this compared to the best result?"

**Example output:**
```
  1. src/auth.py:2  score=0.45 [high]      # Top result = high confidence
  2. src/auth.py:5  score=0.42 [high]      # 93% of top = still high
  3. src/utils.py:1 score=0.35 [medium]    # 78% of top = medium
  4. src/db.py:3    score=0.20 [very_low]  # 44% of top = very_low
```

**Using confidence effectively:**
- High confidence results: Use directly in your response
- Medium confidence: Read the chunk, maybe expand context with `ogrep chunk --context 1`
- Low confidence: The query might need refinement, or the code doesn't exist
- Mixed results (some high, some low): The high confidence ones are likely correct

The `confidence_summary` in stats shows the distribution across all results.

## JSON Output Format

The `--json` flag returns structured data:

```json
{
  "query": "where is authentication handled?",
  "results": [
    {
      "rank": 1,
      "chunk_ref": "src/auth.py:2",
      "chunk_id": 42,
      "path": "/home/user/repo/src/auth.py",
      "relative_path": "src/auth.py",
      "start_line": 61,
      "end_line": 120,
      "score": 0.8523,
      "confidence": "high",
      "language": "python",
      "text": "def authenticate_user(username, password):\n    ..."
    }
  ],
  "stats": {
    "total_results": 15,
    "total_chunks": 1234,
    "search_time_ms": 45,
    "search_mode": "hybrid",
    "fts_available": true,
    "index_model": "text-embedding-3-small",
    "index_dimensions": 1536,
    "refreshed_files": 0,
    "confidence_summary": {
      "high": 3,
      "medium": 7,
      "low": 5,
      "very_low": 0
    }
  }
}
```

**Key fields:**
- `chunk_ref`: Primary reference for `ogrep chunk` command (e.g., `src/auth.py:2`)
- `chunk_id`: Internal ID (also works with `ogrep chunk 42`)
- `confidence`: Human-readable confidence level
- `relative_path`: Easier to read than absolute paths
- `language`: Programming language detected from extension
- `text`: **Full chunk content** (not truncated)
- `fts_available`: Whether hybrid/fulltext search was possible
- `confidence_summary`: Distribution of confidence levels across results
- `refreshed_files`: Number of files reindexed (when using --refresh)

### Chunk Command JSON Output

```json
{
  "requested": {
    "chunk_ref": "src/auth.py:2",
    "chunk_id": 42,
    "chunk_index": 2,
    "path": "/home/user/repo/src/auth.py",
    "relative_path": "src/auth.py",
    "start_line": 61,
    "end_line": 120,
    "language": "python",
    "text": "def authenticate_user(...)..."
  },
  "before": [ /* array of chunk objects */ ],
  "after": [ /* array of chunk objects */ ]
}
```

## Commands Reference

All commands support `--json` for structured output (AI tool integration).

| Command | Description | JSON Support |
|---------|-------------|--------------|
| `ogrep index .` | Index current directory | `--json` |
| `ogrep index . --list` | Preview files (dry run) | `--json` |
| `ogrep query "text" -n 15 --json` | Search (add -r for refresh) | `--json` |
| `ogrep chunk "path:N" -C 1` | Get chunk with context | `--json` (default) |
| `ogrep status` | Show index info | `--json` |
| `ogrep health` | Full database diagnostics | `--json` |
| `ogrep health --vacuum` | Reclaim space and defragment | `--json` |
| `ogrep health --rebuild-fts` | Rebuild FTS5 index | `--json` |
| `ogrep reindex .` | Rebuild index from scratch | `--json` |
| `ogrep reset -f` | Delete index | `--json` |
| `ogrep clean` | Remove stale entries | `--json` |
| `ogrep models` | List embedding models | `--json` |
| `ogrep tune .` | Auto-tune chunk size | `--json` |
| `ogrep benchmark .` | Compare all embedding models | `--json` |

### JSON Output for All Commands

Every command now supports `--json` for programmatic access:

```bash
# Index with JSON output
ogrep index . --json
# Returns: {"status": "success", "files_indexed": 42, "chunks_total": 217, ...}

# Status as JSON
ogrep status --json
# Returns: {"indexed": true, "files": 42, "chunks": 217, "model": "...", ...}

# Clean with JSON output
ogrep clean --json
# Returns: {"status": "success", "removed_count": 3, "removed_paths": [...]}

# Health check as JSON
ogrep health --json
# Returns: {"tables": {...}, "dedup_stats": {...}, "fts5": {...}, ...}

# Models as JSON
ogrep models --json
# Returns: {"models": [{"id": "...", "dimensions": 1536, ...}], ...}
```

## Flag Reference

### Query Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--refresh` | `-r` | Reindex changed files before search |
| `--json` | | Full JSON output (recommended for AI tools) |
| `--mode MODE` | `-M` | Search mode: semantic, fulltext, hybrid |
| `--top N` | `-n` | Number of results (default: 10) |
| `--model MODEL` | `-m` | Embedding model (must match index) |

### Chunk Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--before N` | `-B` | Include N chunks before |
| `--after N` | `-A` | Include N chunks after |
| `--context N` | `-C` | Include N chunks before AND after |

### Index Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--list` | `-l` | Preview files (dry run, doesn't index) |
| `--json` | | Output results as JSON |
| `--exclude PATTERN` | `-e` | Add exclude pattern |
| `--include PATTERN` | `-i` | Override default excludes |
| `--model MODEL` | `-m` | Embedding model |
| `--chunk-lines N` | | Lines per chunk (model-specific default) |
| `--overlap N` | | Overlap between chunks |
| `--no-detect` | | Skip MIME detection (faster) |

### Status/Health/Clean/Reset Flags

| Flag | Description |
|------|-------------|
| `--json` | Output results as JSON |
| `--vacuum` | (clean/health) Compact database |
| `--rebuild-fts` | (health) Rebuild FTS5 index |
| `--integrity` | (health) Full integrity check |
| `--full` | (health) All repairs |
| `-f`, `--force` | (reset) Skip confirmation |

## Environment Variables

### Core Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | Required for OpenAI embeddings |
| `OGREP_BASE_URL` | - | Local server URL (e.g., `http://localhost:1234/v1`) |
| `OGREP_MODEL` | `text-embedding-3-small`* | Default embedding model |
| `OGREP_DIMENSIONS` | model default | Embedding dimensions |

*When `OGREP_BASE_URL` is set, defaults to `nomic-embed-text-v1.5` (local model)

### Chunk Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OGREP_CHUNK_LINES` | model-specific | Lines per chunk (60 for OpenAI, 30 for local) |
| `OGREP_OVERLAP_LINES` | model-specific | Overlap between chunks |
| `OGREP_BATCH_SIZE` | auto-tuned | Batch size for embedding requests |

### Search Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OGREP_SEARCH_MODE` | `hybrid` | Default search mode |
| `OGREP_HYBRID_ALPHA` | `0.7` | Semantic weight in hybrid (0.0-1.0) |

### Confidence Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OGREP_CONFIDENCE_MODE` | `relative` | Mode: `relative` (% of top) or `absolute` |
| `OGREP_RELATIVE_HIGH` | `0.90` | Relative: 90% of top score = high |
| `OGREP_RELATIVE_MEDIUM` | `0.75` | Relative: 75% of top score = medium |
| `OGREP_RELATIVE_LOW` | `0.50` | Relative: 50% of top score = low |
| `OGREP_CONFIDENCE_HIGH` | `0.50` | Absolute: threshold for "high" |
| `OGREP_CONFIDENCE_MEDIUM` | `0.40` | Absolute: threshold for "medium" |
| `OGREP_CONFIDENCE_LOW` | `0.30` | Absolute: threshold for "low" |

## FTS5 Availability

Hybrid and fulltext modes require FTS5 index. If missing:
- Search falls back to semantic mode automatically
- Warning printed to stderr (not in JSON output)
- `fts_available: false` in JSON stats

**To enable hybrid search:**
```bash
ogrep reindex .   # Rebuilds index with FTS5
```

**Check FTS5 status:**
```bash
ogrep health      # Shows "FTS5 Stats" section
```

## Operational Notes

### Model Consistency
- Model must match between index and query
- Run `ogrep status` to check current index model
- Use same `-m` flag or environment variable

### Smart Embedding Reuse
ogrep minimizes API costs through intelligent caching:
- Unchanged files are skipped entirely
- Modified files reuse embeddings for unchanged chunks
- Cross-file deduplication: identical chunks share embeddings

### Local Models (LM Studio)
For offline/free usage:
```bash
export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index . -m nomic   # Uses local model
```

### Token-Aware Batching
Large batches are automatically split to respect model context limits. No configuration needed.

### Database Health
```bash
ogrep health              # Full diagnostics
ogrep health --vacuum     # Reclaim space
ogrep health --integrity  # Full integrity check
```

## Workflow Examples

### Example 1: Initial Search
```bash
# First time setup
ogrep index .
ogrep query "how does the API handle errors" -n 10 --json
```

### Example 2: Deep Dive After Finding Something
```bash
# Found error handling in handler.py:3
ogrep chunk "handler.py:3" --context 2

# Look for related error types
ogrep query "error types" --mode fulltext --json
```

### Example 3: After Editing Files
```bash
# Ensure fresh results after making changes
ogrep query "the function I just modified" --refresh --json
```

### Example 4: Exploring Unknown Codebase
```bash
# Conceptual search first
ogrep query "where is user data stored" --json

# Then keyword search for specifics
ogrep query "UserRepository" --mode fulltext --json

# Expand context on interesting results
ogrep chunk "models/user.py:2" -C 1
```

### Example 5: Debugging Session
```bash
# Find error handling
ogrep query "exception handling for network requests" --json

# Look at surrounding code
ogrep chunk "client.py:4" --before 2 --after 1

# Find all catch blocks
ogrep query "except Exception" --mode fulltext --json
```
