---
name: semantic-grep
description: |
  Semantic code search for conceptual questions. Proactively use when:
  - User asks WHERE something is implemented ("where is X handled", "how does Y work")
  - User needs to understand code behavior vs finding exact names
  - Exact grep would require knowing the right terms first
  Use when appropriate context detected. Trigger with conceptual code questions.
allowed-tools: Bash, Read
---

# Semantic grep workflow (ogrep)

Fast semantic search over local repos using `ogrep` (SQLite index + embeddings).

## Quick Start

```bash
# Index the repo (run once, or after major changes)
ogrep index .

# Semantic search (ALWAYS use --refresh and --json for AI tools)
ogrep query "where is authentication handled?" -n 15 --refresh --json
```

## Search Modes

ogrep supports three search modes via `--mode` (or `-M`):

| Mode | Best For | Example Query |
|------|----------|---------------|
| `semantic` | Conceptual questions | "where is user authentication handled" |
| `fulltext` | Exact identifiers | "def validate_token" |
| `hybrid` | Mixed/unsure (default) | "authenticate user validation" |

**Default behavior:**
- Uses `OGREP_SEARCH_MODE` env var if set
- Falls back to `hybrid` if not set
- Gracefully degrades to `semantic` if FTS5 unavailable

```bash
# Explicit mode selection
ogrep query "authenticate" --mode semantic --json   # Embeddings only
ogrep query "def authenticate" --mode fulltext --json  # Keywords only
ogrep query "user login" --mode hybrid --json       # Combined (default)
```

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
ogrep chunk "auth.py:4" --context 1
```

#### Pattern 4: Quick Keyword Lookup
```bash
# Know exact function name
ogrep query "def process_request" --mode fulltext --json
```

## Confidence Levels

Each result includes a `confidence` level to help you decide how much to trust it:

| Confidence | Score Range | What It Means |
|------------|-------------|---------------|
| `high` | 0.85+ | Trust and use directly |
| `medium` | 0.70-0.84 | Use but verify with context |
| `low` | 0.50-0.69 | Consider alternative queries |
| `very_low` | < 0.50 | Likely not relevant |

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
- `chunk_ref`: Primary reference for `ogrep chunk` command
- `chunk_id`: Internal ID (also works with `ogrep chunk`)
- `confidence`: Human-readable confidence level (high, medium, low, very_low)
- `relative_path`: Easier to read than absolute paths
- `language`: Programming language detected from extension
- `text`: **Full chunk content** (not truncated)
- `fts_available`: Whether hybrid/fulltext search was possible
- `confidence_summary`: Distribution of confidence levels across results

## Commands Reference

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index current directory |
| `ogrep query "text" -n 15 -r --json` | Search with refresh (recommended) |
| `ogrep chunk "path:N" -C 1` | Get chunk with context |
| `ogrep status` | Show index info |
| `ogrep reindex .` | Rebuild index (enables FTS5) |
| `ogrep reset -f` | Delete index |
| `ogrep models` | List embedding models |

## Flag Reference

### Query Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--refresh` | `-r` | Reindex changed files before search |
| `--json` | | Full JSON output (recommended for AI) |
| `--mode MODE` | `-M` | Search mode: semantic, fulltext, hybrid |
| `--top N` | `-n` | Number of results (default: 10) |
| `--model MODEL` | `-m` | Embedding model (must match index) |

### Chunk Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--before N` | `-B` | Include N chunks before |
| `--after N` | `-A` | Include N chunks after |
| `--context N` | `-C` | Include N chunks before AND after |

## IMPORTANT: Always Use --refresh and --json

**When querying from AI tools, ALWAYS use both flags:**

```bash
ogrep query "your search" --refresh --json
```

- `--refresh` checks for changed files and reindexes them before searching
- `--json` returns structured output with full chunk text and metadata

This is especially critical in AI tool contexts where files are being edited
between queries. The `--refresh` operation is fast due to smart embedding reuse.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OGREP_SEARCH_MODE` | `hybrid` | Default search mode |
| `OGREP_HYBRID_ALPHA` | `0.7` | Semantic weight in hybrid (0.0-1.0) |
| `OGREP_CONFIDENCE_HIGH` | `0.85` | Threshold for "high" confidence |
| `OGREP_CONFIDENCE_MEDIUM` | `0.70` | Threshold for "medium" confidence |
| `OGREP_CONFIDENCE_LOW` | `0.50` | Threshold for "low" confidence |
| `OPENAI_API_KEY` | - | Required for embeddings |
| `OGREP_MODEL` | `text-embedding-3-small` | Default embedding model |
| `OGREP_BASE_URL` | - | Local server URL (e.g., LM Studio) |

## FTS5 Availability

Hybrid and fulltext modes require FTS5 index. If missing:
- Search falls back to semantic mode automatically
- Warning printed to stderr (not in JSON output)
- `fts_available: false` in JSON stats

**To enable hybrid search:**
```bash
ogrep reindex .   # Rebuilds index with FTS5
```

## Operational Notes

- Model must match between index and query (use same `-m` flag)
- Run `ogrep status` to check current index model
- Use `ogrep reindex .` after upgrading to get FTS5 support
