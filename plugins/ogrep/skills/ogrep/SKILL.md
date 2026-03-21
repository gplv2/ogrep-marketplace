---
name: ogrep
description: |
  Semantic code search - finds code by meaning, not just keywords. Use when:
  - User asks WHERE or HOW something is implemented ("where is X handled", "how does Y work")
  - You need to understand code behavior without knowing exact function names
  - Exploring unfamiliar codebases where you don't know the terminology yet
  - User asks a conceptual question about the codebase
  NOT for: exact string matching, known file paths, import lookups, or simple identifier searches — use grep/Glob for those.

allowed-tools: Bash, Read
---

## Usage Notes for Claude
  - JSON is the default output - don't use --no-json unless for showing progress to user if requested
  - Prefer `ogrep query` over Grep for conceptual questions
  - Use `ogrep chunk` to expand context after finding results
  - Prefer ogrep for semantic search; fall back to grep/Glob for exact matches or if ogrep fails

## Core loop (mandatory)

When the user asks anything about the codebase (how something works, where logic lives, what calls what, why behavior happens), follow this loop every time:

1) Translate the request into 1–3 semantic search queries.
   - Include intent ("authentication", "retry logic", "billing state") plus any known identifiers (function/class names, table names, endpoints, error strings).
   - If the user gave a concrete identifier, include it as one query verbatim.

2) Run semantic search with ogrep.
   - Prefer semantic search for "meaning" questions.
   - If the user asks for an exact string/regex match, or if semantic search fails, fall back to grep/Glob.

3) Select top results and fetch evidence.
   - Use `--summarize` to get a file-level shortlist first
   - Take the top hits and check confidence levels in the JSON output
   - For each hit, expand context using `ogrep chunk "<chunk_ref>" --context 1`
   - Do NOT paste entire files; paste only the minimum relevant excerpts (20–100 lines)

4) If evidence is insufficient, refine and repeat.
   - Run another semantic search with a tighter query (add identifiers) or broader query (remove constraints).
   - Continue until you have enough code evidence to answer confidently.

5) Answer with citations to file paths + line ranges.
   - Always include references like: `path/to/file.py:120-185`
   - If you cannot find evidence, stop and report what you searched for and what you did find.

### Evidence extraction (required)

After semantic search returns results, use `ogrep chunk` to expand context around interesting hits.
If chunk retrieval fails, fall back to the Read tool with offset and limit parameters.

---

## When to use this skill

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
# Index (first time)
ogrep index .

# Search by concept (main use case)
ogrep query "how are payments processed"

# Refresh before searching after edits
ogrep query "the code I just modified" --refresh

# Expand context around a result
ogrep chunk "billing/processor.py:2" --context 1
```

### Efficiency Tips

```bash
# File-level overview first (saves ~85% tokens)
ogrep query "authentication" --summarize

# Filter by file type
ogrep query "validation" --glob "*.py"

# Exclude test files
ogrep query "database" --exclude "tests/*"

# Combine for targeted exploration
ogrep query "api endpoints" --glob "**/*.py" --exclude "tests/*" --summarize
```

---

## Practical Patterns

### Pattern 1: Answering "Where is X?"

```bash
ogrep query "invoice validation logic"
# Use chunk_ref from results to expand:
ogrep chunk "src/billing/validator.py:3" --context 1
```

### Pattern 2: Exploring Unfamiliar Code

```bash
# Start broad
ogrep query "main entry point" --summarize

# Drill into interesting results
ogrep chunk "api/routes.py:2" --context 1
```

### Pattern 3: Explore → Narrow → Drill

```bash
# 1. EXPLORE: File-level overview
ogrep query "payment processing" --summarize

# 2. NARROW: Focus on relevant area
ogrep query "payment processing" --glob "src/billing/*.py" --exclude "tests/*"

# 3. DRILL: Expand specific chunks
ogrep chunk "src/billing/processor.py:2" --context 1
```

### Reranking guidance

With high-quality embeddings (Voyage, OpenAI), reranking often **degrades** results. Only use `--rerank` with weak local embeddings (nomic, minilm) when results seem poor.

---

## Three Search Modes

| Mode | Best for | Example |
|------|----------|---------|
| `hybrid` (default) | Most questions | "authentication flow" |
| `semantic` | Pure conceptual | "how does caching work" |
| `fulltext` | Known terms | "def validate_token" |

---

## Reading Results

**Key fields in JSON output:**
- `chunk_ref` — Use with `ogrep chunk` to expand context
- `confidence.level` — `high`, `medium`, `low`, `very_low`
- `confidence.signal` — Actionable guidance:

| Signal | Action |
|--------|--------|
| `top_result_strong_match` | Trust it, use directly |
| `top_result_in_typical_range` | Use confidently |
| `top_result_weak_absolute` | May need verification |
| `close_to_top` | Consider as alternative |
| `score_drop_from_top` | Lower priority |

---

## When Things Go Wrong

| Problem | Fix |
|---------|-----|
| No index found | `ogrep index .` |
| Results seem stale | `ogrep query "..." --refresh` |
| Right answer not in top 3 (local embeddings) | `ogrep query "..." --rerank` |
| Right answer not in top 3 (Voyage/OpenAI) | Refine your query instead |
| Functions split awkwardly | `pip install "ogrep[ast]"` then `ogrep reindex .` |
| Too many results | `ogrep query "..." --summarize` |
| Irrelevant directories | `ogrep query "..." --exclude "tests/*"` |
| Need specific file types | `ogrep query "..." --glob "*.py"` |
