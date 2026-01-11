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

**JSON output structure:**
```json
{
  "query": "...",
  "results": [
    {
      "rank": 1,
      "path": "/absolute/path/to/file.py",
      "relative_path": "src/file.py",
      "start_line": 10,
      "end_line": 70,
      "score": 0.85,
      "language": "python",
      "text": "full chunk content..."
    }
  ],
  "stats": {
    "total_results": 15,
    "total_chunks": 1234,
    "search_time_ms": 45,
    "index_model": "nomic",
    "index_dimensions": 768,
    "refreshed_files": 0
  }
}
```

If it fails because the DB doesn't exist:
1) Run `/ogrep:index`
2) Retry the query.
