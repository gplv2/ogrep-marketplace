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
ogrep query "where is user authentication handled"
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

**All commands output JSON by default.** Use `--no-json` for human-readable text.

```bash
# Index (first time - takes a minute)
ogrep index .

# Search by concept (this is the main use case)
ogrep query "how are payments processed"

# After editing files, refresh before searching
ogrep query "the code I just modified" --refresh

# Expand context around an interesting result
ogrep chunk "billing/processor.py:2" --context 1

# Human-readable output (when needed)
ogrep status --no-json
```

---

## Practical Patterns

### Pattern 1: Answering "Where is X?"

User asks: "Where does invoice validation happen?"

```bash
ogrep query "invoice validation logic"
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
ogrep query "main entry point"
ogrep query "how does the API handle requests" -n 15
```

Found something interesting? Drill into it:

```bash
ogrep chunk "api/routes.py:2" --context 1
```

### Pattern 3: Finding Related Code

You found the payment handler, now you need related pieces:

```bash
ogrep query "payment error handling"
ogrep query "payment refund logic"
```

### Pattern 4: Precision Mode with Reranking

Standard search gets you to the neighborhood. Reranking gets you to the exact house.

The problem: semantic search retrieves good candidates, but the #1 result isn't always the best match. Reranking uses a cross-encoder model to re-score the top candidates with much higher precision.

```bash
# Install reranking support (one-time, ~300MB model download)
pip install "ogrep[rerank]"

# Basic reranking - reorders top 50 candidates
ogrep query "database connection pooling" --rerank

# Control how many candidates to rerank
ogrep query "complex auth flow" --rerank --rerank-top 30
```

When to use `--rerank`:
- The right answer appears in results but not at #1
- You need high precision for a complex query
- You're doing a one-off important search (reranking is slower)

---

## Three Search Modes

| Mode | Best for | Example |
|------|----------|---------|
| `hybrid` (default) | Most questions | "authentication flow" |
| `semantic` | Pure conceptual | "how does caching work" |
| `fulltext` | Known terms | "def validate_token" |

```bash
ogrep query "handle errors" --mode semantic
ogrep query "class ErrorHandler" --mode fulltext
ogrep query "error handling logic"  # hybrid (default)
```

---

## AST-Aware Chunking

By default, ogrep splits files into ~60-line chunks with overlap. This can split functions or classes awkwardly:

```
# Line-based chunking (default):
Chunk 1: lines 1-60 (end of ClassA, start of ClassB)
Chunk 2: lines 50-110 (middle of ClassB)
```

AST-aware chunking uses tree-sitter to split by semantic boundaries:

```
# AST chunking (--ast):
Chunk 1: class UserAuth (complete, lines 1-45)
Chunk 2: def validate_token (complete, lines 47-82)
Chunk 3: class SessionManager (complete, lines 84-150)
```

**Supported languages:** Python, JavaScript, TypeScript, TSX, Go, Rust

**Extended languages (with `[ast-all]`):** Ruby, Java, C, C++, C#, Bash

### Using AST Chunking

```bash
# Install AST support
pip install "ogrep[ast]"        # Core languages
pip install "ogrep[ast-all]"    # All languages

# Index with AST chunking
ogrep index . --ast

# Rebuild existing index with AST
ogrep reindex . --ast

# Check if AST is being used
ogrep status
```

**When to use AST chunking:**
- Codebases with large functions/classes that shouldn't be split
- When search results show awkward partial matches
- Languages with clear semantic boundaries (functions, classes, methods)

**Fallback behavior:**
- Unsupported file types → line-based chunking
- Parse errors → line-based chunking
- Very large functions (>150 lines) → split with overlap

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
    "language": "python",
    "text": "def authenticate_user(username, password):..."
  }],
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
- `chunk_ref` - Use with `ogrep chunk` to expand context
- `confidence` - `high` (90%+ of top score), `medium`, `low`, `very_low`
- `reranked` - Whether results were reranked with cross-encoder
- `text` - Full chunk content for analysis

---

## Expanding Context

Query found something interesting? Get more:

```bash
# Surrounding context (1 chunk before and after)
ogrep chunk "auth.py:2" --context 1

# What comes before (find class definition)
ogrep chunk "models/user.py:5" --before 2

# What comes after (see what follows)
ogrep chunk "handler.py:3" --after 1
```

**chunk_ref format:** `"file.py:N"` where N is chunk index (0-based)

---

## Index Management

```bash
# Create new index
ogrep index .
ogrep index . --ast              # With AST chunking

# Rebuild from scratch
ogrep reindex .
ogrep reindex . --ast            # Rebuild with AST

# Update changed files only
ogrep refresh .

# Check index status
ogrep status

# View recent changes
ogrep log --limit 10

# Database health
ogrep health

# Clean up stale entries
ogrep clean
ogrep clean --vacuum             # Also compact database
```

---

## When Things Go Wrong

**"No index found"**
```bash
ogrep index .
```

**"Results seem stale"**
```bash
ogrep query "..." --refresh      # Reindexes changed files first
```

**"Right answer is in results but not #1"**
```bash
pip install "ogrep[rerank]"      # If not installed
ogrep query "..." --rerank
```

**"Functions are being split awkwardly"**
```bash
pip install "ogrep[ast]"         # If not installed
ogrep reindex . --ast
```

**"Check index health"**
```bash
ogrep status
ogrep health
```

---

## Command Summary

All commands output JSON by default. Use `--no-json` for human-readable text.

| Task | Command |
|------|---------|
| Create index | `ogrep index .` |
| Create index (AST) | `ogrep index . --ast` |
| Find implementation | `ogrep query "how does X work"` |
| Find exact name | `ogrep query "def function_name" --mode fulltext` |
| Precision search | `ogrep query "..." --rerank` |
| Fresh results | `ogrep query "..." --refresh` |
| More context | `ogrep chunk "file.py:N" --context 1` |
| Rebuild index | `ogrep reindex .` |
| Index status | `ogrep status` |
| Recent changes | `ogrep log --limit 5` |
| Health check | `ogrep health` |
| Clean stale | `ogrep clean` |
| Human output | `ogrep status --no-json` |

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | - | Required for embeddings |
| `OGREP_BASE_URL` | - | Local embeddings server (e.g., LM Studio) |
| `OGREP_SEARCH_MODE` | `hybrid` | Default search mode |
| `OGREP_FUSION_METHOD` | `rrf` | Hybrid fusion (`rrf` or `alpha`) |
| `OGREP_RRF_K` | `60` | RRF smoothing constant |
| `OGREP_RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | Cross-encoder model |
| `OGREP_RERANK_TOPN` | `50` | Default candidates to rerank |
| `OGREP_AST_CHUNKING` | - | Enable AST chunking globally (`1` or `true`) |

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
