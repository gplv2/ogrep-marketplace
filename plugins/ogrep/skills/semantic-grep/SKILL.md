---
name: semantic-grep
description: |
  Semantic code search - finds code by meaning, not just keywords. Helpful when:
  - User asks WHERE something is implemented ("where is X handled", "how does Y work")
  - You need to understand code behavior without knowing exact function names
  - Exploring unfamiliar codebases where you don't know the terminology yet
allowed-tools: Bash, Read
---

# ogrep - When grep isn't enough

You're looking for authentication code. Is it called `authenticate`, `login`, `verify_credentials`, `check_token`, or `validate_session`? With grep, you'd have to guess. With ogrep, you just ask.

```bash
ogrep query "where is user authentication handled" --json
```

## The Sweet Spot

ogrep fills a specific gap: **conceptual code questions**.

| Use ogrep when... | Use grep/Glob when... |
|-------------------|----------------------|
| "Where is error handling done?" | `class ErrorHandler` |
| "How does caching work here?" | `def get_cache` |
| "What validates user input?" | `validate_email` |
| Exploring unfamiliar code | You know the exact term |
| User asks a conceptual question | Looking for imports/strings |

**Rule of thumb:** If you'd need to guess multiple terms for grep, try ogrep first.

---

## Quick Reference

```bash
# Index (first time - takes a minute)
ogrep index .

# Search by concept (this is the main use case)
ogrep query "how are payments processed" --json

# After editing files, refresh before searching
ogrep query "the code I just modified" --refresh --json

# Expand context around an interesting result
ogrep chunk "billing/processor.py:2" --context 1 --json
```

---

## Practical Patterns

### Pattern 1: Answering "Where is X?"

User asks: "Where does invoice validation happen?"

```bash
ogrep query "invoice validation logic" --json
```

Returns results ranked by relevance. The `chunk_ref` field lets you expand context:

```json
{
  "results": [{
    "rank": 1,
    "chunk_ref": "src/billing/validator.py:3",
    "confidence": "high",
    "text": "def validate_invoice(invoice: Invoice) -> ValidationResult:..."
  }]
}
```

### Pattern 2: Exploring Unfamiliar Code

You've never seen this codebase. Start broad:

```bash
ogrep query "main entry point" --json
ogrep query "how does the API handle requests" -n 15 --json
```

Found something interesting? Drill into it:

```bash
ogrep chunk "api/routes.py:2" --context 1 --json
```

### Pattern 3: Finding Related Code

You found the payment handler, now you need related pieces:

```bash
ogrep query "payment error handling" --json
ogrep query "payment refund logic" --json
```

### Pattern 4: Precision Mode

Standard search gets you to the neighborhood. Reranking gets you to the house:

```bash
# When you need the best result to be #1 (requires pip install "ogrep[rerank]")
ogrep query "database connection pooling" --rerank --json
```

---

## Three Search Modes

| Mode | Best for | Example |
|------|----------|---------|
| `hybrid` (default) | Most questions | "authentication flow" |
| `semantic` | Pure conceptual | "how does caching work" |
| `fulltext` | Known terms | "def validate_token" |

```bash
ogrep query "handle errors" --mode semantic --json
ogrep query "class ErrorHandler" --mode fulltext --json
```

---

## Reading Results

```json
{
  "results": [{
    "rank": 1,
    "chunk_ref": "src/auth.py:2",
    "path": "/repo/src/auth.py",
    "start_line": 61,
    "end_line": 120,
    "score": 0.032,
    "confidence": "high",
    "text": "def authenticate_user(username, password):..."
  }],
  "stats": {
    "search_mode": "hybrid",
    "reranked": false,
    "confidence_summary": {"high": 2, "medium": 5, "low": 3}
  }
}
```

**Key fields:**
- `chunk_ref` - Use with `ogrep chunk` to expand context
- `confidence` - `high` means 90%+ of top score, trust it
- `text` - Full chunk content for analysis

---

## Expanding Context

Query found something interesting? Get more:

```bash
# Surrounding context
ogrep chunk "auth.py:2" --context 1 --json

# What comes before (find class definition)
ogrep chunk "models/user.py:5" --before 2 --json

# What comes after (see what follows)
ogrep chunk "handler.py:3" --after 1 --json
```

**chunk_ref format:** `"file.py:N"` where N is chunk index (0-based, ~60 lines each)

---

## Optional Features

### AST-Aware Chunking

Better semantic boundaries - chunks by function/class instead of line counts:

```bash
pip install "ogrep[ast]"  # One-time

ogrep index . --ast                 # New index with AST chunking
ogrep reindex . --ast               # Rebuild existing index
```

Improves results for codebases where functions should stay together.

### Cross-Encoder Reranking

When precision matters more than speed:

```bash
pip install "ogrep[rerank]"  # One-time (~300MB model download)

ogrep query "complex topic" --rerank --json
ogrep query "..." --rerank-top 30 --json  # Rerank top 30 candidates
```

---

## When Things Go Wrong

**"No index found"**
```bash
ogrep index .  # Creates .ogrep/index.sqlite
```

**"Results seem stale"**
```bash
ogrep query "..." --refresh --json  # Reindexes changed files first
```

**"Right answer is in results but not #1"**
```bash
ogrep query "..." --rerank --json   # Better precision ranking
```

**"Check index health"**
```bash
ogrep status --json
ogrep health --json
```

---

## Command Summary

| Task | Command |
|------|---------|
| Find implementation | `ogrep query "how does X work" --json` |
| Find exact name | `ogrep query "def function_name" --mode fulltext --json` |
| Fresh results | `ogrep query "..." --refresh --json` |
| More context | `ogrep chunk "file.py:N" --context 1 --json` |
| Precision search | `ogrep query "..." --rerank --json` |
| What changed | `ogrep log --limit 5 --json` |
| Health check | `ogrep health --json` |
| Full rebuild | `ogrep reindex .` |

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | - | Required for embeddings |
| `OGREP_BASE_URL` | - | Local embeddings server |
| `OGREP_SEARCH_MODE` | `hybrid` | Default search mode |
| `OGREP_FUSION_METHOD` | `rrf` | Hybrid fusion (rrf or alpha) |

**Local embeddings (optional):**
```bash
export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index . -m nomic
```

---

## Why This Tool Exists

Traditional search requires knowing exact terms. But when exploring unfamiliar code or mapping user questions to implementation, you often don't know what you're looking for until you find it.

ogrep bridges that gap - turning "where is authentication handled" into actual code, regardless of what the developer named things.

It won't replace grep. It's the tool you reach for when grep requires too much guessing.
