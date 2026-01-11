# ogrep v0.5.0 Release Notes

## What's New

### Hybrid Search (Phase 2)

ogrep now combines semantic search with keyword matching for the best of both worlds:

```bash
ogrep query "authenticate user" --mode hybrid --json
```

| Mode | Best For | Example |
|------|----------|---------|
| `semantic` | Conceptual questions | "where is auth handled" |
| `fulltext` | Exact identifiers | "def validate_token" |
| `hybrid` | Mixed/unsure (default) | "authenticate user validation" |

Set default via environment:
```bash
export OGREP_SEARCH_MODE=hybrid  # semantic, fulltext, or hybrid
export OGREP_HYBRID_ALPHA=0.7    # 70% semantic, 30% keyword weight
```

### Chunk Navigation (Phase 2)

Found something interesting? Expand context without reading entire files:

```bash
# Get a chunk by reference (from query results)
ogrep chunk "src/auth.py:2"

# Get surrounding context
ogrep chunk "src/auth.py:2" --before 1    # + 1 chunk before
ogrep chunk "src/auth.py:2" --after 1     # + 1 chunk after
ogrep chunk "src/auth.py:2" --context 1   # + 1 before AND after
```

Query results now include `chunk_ref` for easy navigation:
```json
{
  "results": [
    {
      "chunk_ref": "src/auth.py:2",
      "chunk_id": 42,
      ...
    }
  ]
}
```

### Confidence Scoring (Phase 3)

Each result now tells you how much to trust it:

| Confidence | Score | Guidance |
|------------|-------|----------|
| `high` | 0.85+ | Trust and use directly |
| `medium` | 0.70-0.84 | Use but verify with context |
| `low` | 0.50-0.69 | Consider alternative queries |
| `very_low` | <0.50 | Likely not relevant |

JSON output includes confidence for each result:
```json
{
  "results": [
    {
      "score": 0.89,
      "confidence": "high",
      ...
    }
  ],
  "stats": {
    "confidence_summary": {"high": 3, "medium": 5, "low": 2, "very_low": 0}
  }
}
```

Human-readable output also shows confidence:
```
/path/file.py:10-70  score=0.8523 (high)
```

Customize thresholds via environment:
```bash
export OGREP_CONFIDENCE_HIGH=0.85
export OGREP_CONFIDENCE_MEDIUM=0.70
export OGREP_CONFIDENCE_LOW=0.50
```

### FTS5 Full-Text Search Index

Hybrid and fulltext modes use SQLite FTS5 for fast keyword matching. Enable it by reindexing:

```bash
ogrep reindex .
```

If FTS5 isn't available, ogrep gracefully falls back to semantic-only search.

## Environment Variables Summary

| Variable | Default | Description |
|----------|---------|-------------|
| `OGREP_SEARCH_MODE` | `hybrid` | Default search mode |
| `OGREP_HYBRID_ALPHA` | `0.7` | Semantic weight (0.0-1.0) |
| `OGREP_CONFIDENCE_HIGH` | `0.85` | High confidence threshold |
| `OGREP_CONFIDENCE_MEDIUM` | `0.70` | Medium confidence threshold |
| `OGREP_CONFIDENCE_LOW` | `0.50` | Low confidence threshold |

## Upgrading

```bash
pip install --upgrade ogrep
# or
pip install --force-reinstall git+https://github.com/gplv2/ogrep.git

# Enable hybrid search by rebuilding index
ogrep reindex .
```

## Documentation

- [README.md](README.md) - Quick start and overview
- [LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md) - Detailed local model setup
- [CHANGELOG.md](CHANGELOG.md) - Full technical changelog

## Links

- GitHub: https://github.com/gplv2/ogrep-marketplace
