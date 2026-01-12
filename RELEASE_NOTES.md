# ogrep v0.6.3 Release Notes

## What's New

### JSON Output for All Commands

Every ogrep command now supports `--json` for structured output, making it easy to integrate with AI tools and scripts:

```bash
# Index with JSON output
ogrep index . --json
# Returns: {"status": "success", "files_indexed": 42, "chunks_total": 217, ...}

# Status as JSON
ogrep status --json
# Returns: {"indexed": true, "files": 42, "chunks": 217, "model": "...", ...}

# Clean with JSON output
ogrep clean --json
# Returns: {"status": "success", "removed_count": 3, "removed_paths": [...]}

# Health check as JSON
ogrep health --json
# Returns: {"tables": {...}, "dedup_stats": {...}, "fts5": {...}, ...}

# Models list as JSON
ogrep models --json
# Returns: {"models": [{"id": "...", "dimensions": 1536, ...}], ...}

# Reset with JSON output
ogrep reset -f --json
# Returns: {"status": "success", "database": "...", "removed": true, ...}

# Reindex with JSON output
ogrep reindex . --json
# Returns: {"status": "success", "files_indexed": 42, "chunks_embedded": 217, ...}

# Tune with JSON output
ogrep tune . --json
# Returns: {"recommended_chunk_lines": 60, "results": [...], ...}
```

### Query Input Validation

ogrep now validates query input before making API calls:

```bash
ogrep query ""
# Error: Query too short: '' (0 chars). Minimum is 2 characters.

ogrep query "a"
# Error: Query too short: 'a' (1 chars). Minimum is 2 characters.
```

JSON output includes error codes for programmatic handling:
```json
{"error": "Query too short: 'a' (1 chars). Minimum is 2 characters.", "error_code": "QUERY_TOO_SHORT"}
```

### YAML Files Now Indexed

YAML configuration files (`*.yaml`, `*.yml`) are now indexed by default. This makes it easy to search for configuration values, CI/CD pipelines, Kubernetes manifests, and other YAML-based definitions.

### Search Modes Reminder

ogrep supports three search modes via `--mode` (or `-M`):

| Mode | Best For | Example |
|------|----------|---------|
| `semantic` | Conceptual questions | "where is auth handled" |
| `fulltext` | Exact identifiers | "def validate_token" |
| `hybrid` | Mixed/unsure (default) | "authenticate user validation" |

```bash
ogrep query "authenticate" --mode semantic --json   # Embeddings only
ogrep query "def authenticate" --mode fulltext --json  # Keywords only
ogrep query "user login" --mode hybrid --json       # Combined (default)
```

### Configurable Confidence Thresholds

Confidence thresholds are now configurable via environment variables:

```bash
# Lower thresholds for sparse/legacy codebases
export OGREP_CONFIDENCE_HIGH=0.60    # default: 0.85
export OGREP_CONFIDENCE_MEDIUM=0.45  # default: 0.70
export OGREP_CONFIDENCE_LOW=0.35     # default: 0.50
```

| Confidence | Default Threshold | Guidance |
|------------|-------------------|----------|
| `high` | 0.85+ | Trust and use directly |
| `medium` | 0.70-0.84 | Use but verify with context |
| `low` | 0.50-0.69 | Consider alternative queries |
| `very_low` | <0.50 | Likely not relevant |

## Commands with JSON Support

| Command | JSON Flag | Key Output Fields |
|---------|-----------|-------------------|
| `ogrep index` | `--json` | files_indexed, chunks_total, chunks_reused, tokens_saved |
| `ogrep query` | `--json` | results[], stats{}, confidence_summary{} |
| `ogrep chunk` | `--json` | requested{}, before[], after[] |
| `ogrep status` | `--json` | indexed, files, chunks, model, dimensions, size_bytes |
| `ogrep health` | `--json` | tables{}, dedup_stats{}, fts5{}, sqlite_info{} |
| `ogrep clean` | `--json` | removed_count, removed_paths[], vacuumed |
| `ogrep reset` | `--json` | removed, database, size_bytes |
| `ogrep reindex` | `--json` | files_indexed, chunks_total, chunks_embedded |
| `ogrep models` | `--json` | models[], current_model, env_vars{} |
| `ogrep tune` | `--json` | recommended_chunk_lines, results[] |
| `ogrep benchmark` | `--json` | models[], recommended{} |

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

# Rebuild index to include YAML files
ogrep reindex .
```

## Documentation

- [README.md](README.md) - Quick start and overview
- [LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md) - Detailed local model setup
- [CHANGELOG.md](CHANGELOG.md) - Full technical changelog

## Links

- GitHub: https://github.com/gplv2/ogrep-marketplace
