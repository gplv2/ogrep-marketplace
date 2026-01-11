---
description: Run a semantic query over the local SQLite index and return top matches
allowed-tools: Bash
argument-hint: <query text>
---

Run:
- `ogrep query "$ARGUMENTS" --top 15 --refresh --json`

**Flags explained:**
- `--refresh` ensures results reflect current code by checking for changed files and reindexing them before querying
- `--json` returns structured output with full chunk text, language detection, and metadata
- `--mode MODE` (optional) selects search mode: `semantic`, `fulltext`, or `hybrid` (default)

**Search modes:**
- `semantic`: Embedding similarity only (conceptual questions)
- `fulltext`: FTS5 keyword matching (exact identifiers)
- `hybrid`: Combined scoring (default, best of both)

**JSON output structure:**
```json
{
  "query": "...",
  "results": [
    {
      "rank": 1,
      "chunk_ref": "src/file.py:2",
      "chunk_id": 42,
      "path": "/absolute/path/to/file.py",
      "relative_path": "src/file.py",
      "start_line": 10,
      "end_line": 70,
      "score": 0.85,
      "confidence": "high",
      "language": "python",
      "text": "full chunk content..."
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
    "confidence_summary": {"high": 3, "medium": 5, "low": 2, "very_low": 0}
  }
}
```

**Using chunk_ref:** After finding a result, use `ogrep chunk "src/file.py:2"` to get more context.

If it fails because the DB doesn't exist:
1) Run `/ogrep:index`
2) Retry the query.
