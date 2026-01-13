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

# ogrep - Semantic Code Search

**The problem:** You need to find where authentication is handled, but you don't know if it's called `authenticate`, `login`, `verify_credentials`, `auth_handler`, or something else entirely. Grep requires knowing the exact term. Ogrep doesn't.

**What ogrep does:** Searches code by *meaning*, not just keywords. It understands that "where is authentication handled" might match code containing `verify_password`, `check_token`, or `validate_session`.

## When to Reach for ogrep

| Situation | Why ogrep helps |
|-----------|-----------------|
| "Where is X implemented?" | Don't need to guess the function name |
| "How does this work?" | Finds conceptually related code |
| Unfamiliar codebase | Explores without knowing terminology |
| User asks a question | Maps their words to code constructs |
| Need to understand flow | Finds related pieces across files |

**When grep is still better:** Exact function names, specific strings, known identifiers.

## Quick Start

```bash
# Index once (creates .ogrep/index.sqlite)
ogrep index .

# Search by concept
ogrep query "how are users authenticated" --json

# Search after editing files (ensure fresh results)
ogrep query "the code I just modified" --refresh --json
```

---

## Real Examples

### Finding Implementation You Can't Name

**Problem:** User asks "where are invoices generated?"

With grep, you'd have to guess: `generate_invoice`? `create_invoice`? `InvoiceBuilder`? `bill_customer`?

```bash
ogrep query "invoice generation logic" --json
```

Returns code that handles invoice creation, regardless of naming conventions.

### Understanding Unfamiliar Code

**Problem:** You've never seen this codebase. User asks about the payment flow.

```bash
# Start broad
ogrep query "payment processing flow" -n 15 --json

# Then drill into specifics
ogrep query "def charge" --mode fulltext --json

# Expand context around interesting results
ogrep chunk "billing/processor.py:3" --context 1 --json
```

### After Editing Files

**Problem:** You modified some code. Need to search fresh.

```bash
ogrep query "error handling" --refresh --json
```

The `--refresh` flag reindexes changed files before searching. Fast due to embedding reuse.

### Precision Mode with Reranking

**Problem:** Right answer is in top 30, but not #1.

```bash
# Install reranking support (one-time)
pip install "ogrep[rerank]"

# Enable precision reranking
ogrep query "database connection pooling" --rerank --json
```

Reranking uses a cross-encoder to reorder results for better precision.

---

## Three Search Modes

| Mode | Use When | Example |
|------|----------|---------|
| `hybrid` (default) | Best of both worlds | `"authentication flow"` |
| `semantic` | Conceptual questions | `"how does caching work"` |
| `fulltext` | Known identifiers | `"def validate_token"` |

```bash
ogrep query "handle errors" --mode semantic --json
ogrep query "class ErrorHandler" --mode fulltext --json
ogrep query "error handling logic" --json  # hybrid (default)
```

---

## Expanding Context

Query finds something interesting? Get more context:

```bash
# Get chunk with surrounding code
ogrep chunk "auth.py:2" --context 1 --json

# See what comes before (find class definition)
ogrep chunk "models/user.py:5" --before 2 --json

# See what comes after (find what calls this)
ogrep chunk "handler.py:3" --after 1 --json
```

**chunk_ref format:** `"path/to/file.py:N"` where N is chunk index (0-based, ~60 lines each)

---

## JSON Output

All commands support `--json` for structured results:

```bash
ogrep query "where is auth" --json
```

```json
{
  "query": "where is auth",
  "results": [
    {
      "rank": 1,
      "chunk_ref": "src/auth.py:2",
      "path": "/repo/src/auth.py",
      "start_line": 61,
      "end_line": 120,
      "score": 0.032,
      "confidence": "high",
      "language": "python",
      "text": "def authenticate_user(username, password):\n    ..."
    }
  ],
  "stats": {
    "total_results": 10,
    "search_mode": "hybrid",
    "fusion_method": "rrf",
    "reranked": false,
    "confidence_summary": {"high": 2, "medium": 5, "low": 3}
  }
}
```

**Key fields:**
- `chunk_ref`: Use with `ogrep chunk` to get more context
- `confidence`: `high` (90%+ of top score), `medium`, `low`, `very_low`
- `text`: Full chunk content, not truncated

---

## Confidence Levels

Results are ranked relative to the best match:

| Confidence | What it means |
|------------|---------------|
| `high` | 90%+ of top score - trust it |
| `medium` | 75-89% - use but verify |
| `low` | 50-74% - maybe try different query |
| `very_low` | < 50% - probably not relevant |

Why relative? Cosine similarity clusters around 0.3-0.5, so a score of 0.45 is actually excellent. Relative scoring tells you "how good is this compared to the best result?"

---

## Command Reference

### Essential Commands

```bash
# Index (first time or major changes)
ogrep index .

# Search
ogrep query "your question" --json
ogrep query "your question" --refresh --json   # After editing files
ogrep query "exact name" --mode fulltext --json

# Expand context
ogrep chunk "file.py:N" --context 1 --json

# Check status
ogrep status --json
```

### Reranking (Optional Precision)

```bash
pip install "ogrep[rerank]"  # One-time install

ogrep query "complex topic" --rerank --json
ogrep query "..." --rerank-top 30 --json  # Rerank top 30 candidates
```

### Maintenance

```bash
ogrep log --limit 5 --json    # See what changed recently
ogrep health --json           # Database diagnostics
ogrep clean --vacuum          # Reclaim space
ogrep reindex .               # Full rebuild
```

---

## Practical Patterns

### Pattern 1: Start Broad, Then Drill Down

```bash
# Conceptual search
ogrep query "how does the API validate requests" -n 15 --json

# Found something in validator.py - get more context
ogrep chunk "validator.py:2" --context 1 --json

# Find exact function names
ogrep query "def validate_" --mode fulltext --json
```

### Pattern 2: Chase the Implementation

```bash
# Find where something is called
ogrep query "user authentication flow" --json

# Then find the actual implementation
ogrep query "def authenticate" --mode fulltext --json

# Expand to see the full function
ogrep chunk "auth.py:3" --after 1 --json
```

### Pattern 3: After User Edits

```bash
# Always use --refresh when user might have changed files
ogrep query "the config I was looking at" --refresh --json
```

### Pattern 4: When Precision Matters

```bash
# Standard search gets you to the neighborhood
ogrep query "database connection pooling" --json

# Reranking gets you to the exact house
ogrep query "database connection pooling" --rerank --json
```

### Pattern 5: Exploring Unknown Territory

```bash
# What's in this codebase?
ogrep query "main entry point" --json
ogrep query "how does error handling work" --json
ogrep query "where is configuration loaded" --json

# Walk through a file
ogrep chunk "main.py:0" --json                    # Start
ogrep chunk "main.py:0" --after 3 --json          # First 4 chunks
```

---

## Environment Variables

| Variable | Default | What it does |
|----------|---------|--------------|
| `OPENAI_API_KEY` | - | Required for OpenAI embeddings |
| `OGREP_BASE_URL` | - | Local server (e.g., LM Studio) |
| `OGREP_SEARCH_MODE` | `hybrid` | Default search mode |
| `OGREP_FUSION_METHOD` | `rrf` | Hybrid fusion method |
| `OGREP_RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | Cross-encoder model |

**Local embeddings:**
```bash
export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index . -m nomic
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Find implementation | `ogrep query "how does X work" --json` |
| Find exact name | `ogrep query "def function_name" --mode fulltext --json` |
| Fresh results | `ogrep query "..." --refresh --json` |
| More context | `ogrep chunk "file.py:N" --context 1 --json` |
| Precision search | `ogrep query "..." --rerank --json` |
| What changed | `ogrep log --limit 5 --json` |
| Health check | `ogrep health --json` |

---

## Why This Tool Exists

Traditional code search requires knowing the exact terms. But when you're:
- Exploring unfamiliar code
- Mapping user questions to implementation
- Looking for conceptual patterns

...you often don't know what you're looking for until you find it.

ogrep bridges the gap between "what the user asked" and "what the code is actually called."

**The goal:** Spend less time guessing function names, more time understanding code.
