---
description: Run a semantic query over the local SQLite index and return top matches
allowed-tools: Bash
argument-hint: <query text>
---

Run:
- `ogrep query "$ARGUMENTS" --top 15 --refresh`

**Flags explained:**
- `--refresh` ensures results reflect current code by checking for changed files and reindexing them before querying
- JSON output is the default (use `--no-json` for human-readable text)
- `--mode MODE` (optional) selects search mode: `semantic`, `fulltext`, or `hybrid` (default)
- `--branch BRANCH` (optional) query a specific branch instead of current branch
- `--summarize` (optional) return file-level overview instead of full chunks (~85% token savings)
- `--glob PATTERN` (optional) filter results to matching files (e.g., `--glob "*.py"`)
- `--exclude PATTERN` (optional) exclude matching files (e.g., `--exclude "tests/*"`)

**Search modes:**
- `semantic`: Embedding similarity only (conceptual questions)
- `fulltext`: FTS5 keyword matching (exact identifiers)
- `hybrid`: Combined scoring (default, best of both)

**Cross-branch queries:**
```bash
# Query current branch (default)
ogrep query "authentication"

# Query a specific branch
ogrep query "authentication" --branch main
```

**JSON output structure:**
```json
{
  "query": "...",
  "results": [
    {
      "rank": 1,
      "chunk_ref": "src/file.py:2",
      "path": "/absolute/path/to/file.py",
      "relative_path": "src/file.py",
      "start_line": 10,
      "end_line": 70,
      "score": 0.42,
      "confidence": {
        "level": "high",
        "signal": "top_result_in_typical_range"
      },
      "language": "python",
      "text": "full chunk content..."
    }
  ],
  "stats": {
    "total_results": 15,
    "search_mode": "hybrid",
    "confidence_summary": {"high": 3, "medium": 5, "low": 2}
  }
}
```

**Confidence signals:** `top_result_strong_match` (trust it), `top_result_in_typical_range` (good), `top_result_weak_absolute` (verify), `close_to_top` (alternative), `score_drop_from_top` (lower priority)

**Using chunk_ref:** After finding a result, use `ogrep chunk "src/file.py:2"` to get more context.

If it fails because the DB doesn't exist:
1) Run `/ogrep:index`
2) Retry the query.
