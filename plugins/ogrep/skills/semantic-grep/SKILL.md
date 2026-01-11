---
name: semantic-grep
description: |
  Semantic code search for conceptual questions. Proactively use when:
  - User asks WHERE something is implemented ("where is X handled", "how does Y work")
  - User needs to understand code behavior vs finding exact names
  - Exact grep would require knowing the right terms first
  Use when appropriate context detected. Trigger with conceptual code questions.
allowed-tools: Bash, Read
---

# Semantic grep workflow (ogrep)

Fast semantic search over local repos using `ogrep` (SQLite index + OpenAI embeddings).

## Quick Start

```bash
# Index the repo (run once, or after major changes)
ogrep index .

# Semantic search (ALWAYS use --refresh and --json for AI tools)
ogrep query "where is authentication handled?" -n 15 --refresh --json
```

## IMPORTANT: Always Use --refresh and --json

**When querying from AI tools, ALWAYS use both flags:**

```bash
ogrep query "your search" --refresh --json
```

- `--refresh` checks for changed files and reindexes them before searching.
  Without it, queries may return stale results based on outdated embeddings.
- `--json` returns structured output with full chunk text, language detection,
  and metadata. Much better for AI tools than truncated human-readable output.

This is especially critical in AI tool contexts where files are being edited
between queries. The `--refresh` operation is fast due to smart embedding reuse.

## JSON Output Format

The `--json` flag returns structured data:

```json
{
  "query": "where is authentication handled?",
  "results": [
    {
      "rank": 1,
      "path": "/home/user/repo/auth.py",
      "relative_path": "auth.py",
      "start_line": 10,
      "end_line": 70,
      "score": 0.8523,
      "language": "python",
      "text": "def authenticate_user(username, password):\n    ..."
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

**Key fields:**
- `relative_path`: Easier to read than absolute paths
- `language`: Programming language detected from extension
- `text`: **Full chunk content** (not truncated like human output)
- `stats`: Metadata about the search and index

## Smart Defaults

**Source-only indexing** - By default, ogrep indexes only source code:
- Excludes: `*.md`, `*.json`, `*.yaml`, `*.toml`, `docs/*`, `vendor/*`, etc.
- Skips: `.git/`, `node_modules/`, `.venv/`, `__pycache__/`

**Optimal chunk size** - 60 lines with 10-line overlap (tested for best relevance).

## Commands

| Command | Description |
|---------|-------------|
| `ogrep index .` | Index current directory |
| `ogrep query "text" -n 15 -r` | Semantic search with refresh |
| `ogrep status` | Show index info |
| `ogrep reset -f` | Delete index |
| `ogrep models` | List embedding models |

## Override Defaults

```bash
# Include markdown files (normally excluded)
ogrep index . -i '*.md'

# Add extra exclusions
ogrep index . -e 'test_*' -e 'fixtures/*'

# Use high-accuracy model (slower, more expensive)
ogrep index . -m large
```

## Alternative: Claude Code Hooks

Instead of using `--refresh` on every query, you can configure Claude Code
to automatically reindex after file edits using hooks.

### Hook Configuration

Create or edit `.claude/settings.json` in your project root:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "command": "ogrep index . --quiet 2>/dev/null || true"
      }
    ]
  }
}
```

**Hook file locations:**
- **Project-specific**: `.claude/settings.json` (in your repo root)
- **User-global**: `~/.claude/settings.json`

### When to Use Hooks vs --refresh

| Approach | Pros | Cons |
|----------|------|------|
| `--refresh` flag | Works everywhere, no config needed | Small latency on each query |
| Claude Code hooks | Zero query latency | Requires Claude Code, hook config |

**Recommendation**: Use `--refresh` as the default approach. Add hooks as an
optimization if query latency becomes noticeable.

## Operational Notes

- Requires `OPENAI_API_KEY` in environment
- Model must match between index and query (use same `-m` flag)
- Run `ogrep status` to check current index model
- Without `--refresh`, embeddings may be stale after file edits
