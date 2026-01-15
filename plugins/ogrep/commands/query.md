---
description: Run a semantic query over the local SQLite index and return top matches
allowed-tools: Bash
argument-hint: <query text>
---

Run:
- `ogrep query "$ARGUMENTS" -n 15 --refresh`

**Core flags:**
| Flag | Alias | Default | Purpose |
|------|-------|---------|---------|
| `--top` | `-n` | 10 | Number of results to return |
| `--refresh` | `-r` | off | Reindex changed files before querying (recommended) |
| `--mode` | `-M` | hybrid | Search mode: `semantic`, `fulltext`, or `hybrid` |
| `--rerank` | - | off | Apply cross-encoder for higher precision (slower) |
| `--rerank-top` | - | 50 | Candidates to rerank (implies `--rerank`) |

**Output flags:**
| Flag | Default | Purpose |
|------|---------|---------|
| `--json` | yes | JSON output (default for AI/machine use) |
| `--no-json` | - | Human-readable text output |

**Search modes:**
- `hybrid` (default): Combined semantic + keyword scoring - best for most queries
- `semantic`: Embedding similarity only - for conceptual questions ("how does X work")
- `fulltext`: FTS5 keyword matching - for exact identifiers ("class AuthMiddleware")

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
    "fusion_method": "rrf",
    "reranked": false,
    "ast_mode": true,
    "fts_available": true,
    "index_model": "text-embedding-3-small",
    "index_dimensions": 1536,
    "confidence_summary": {"high": 3, "medium": 5, "low": 2, "very_low": 0}
  }
}
```

**Using chunk_ref:** The `chunk_ref` (e.g., `"src/file.py:2"`) is a 0-based chunk index, NOT a line number. Use `ogrep chunk "src/file.py:2" --context 1` to expand context around a result.

**Advanced flags:**
| Flag | Purpose |
|------|---------|
| `--db PATH` | Explicit SQLite DB path (overrides scope options) |
| `--profile NAME` | Named profile for multiple indexes per repo |
| `--global-cache` | Use `~/.cache/ogrep/<repo_hash>/index.sqlite` |
| `--repo-root PATH` | Explicit repository root |
| `--model`, `-m` | Embedding model (must match indexed model) |
| `--dimensions`, `-d` | Embedding dimensions |

**If query fails with "no index":**
1. Run `/ogrep:index` first
2. Retry the query
