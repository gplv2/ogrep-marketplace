---
name: semantic-grep
description: Semantic grep for a repo. Use when the user asks to "search by meaning", "find where this is implemented", "grep semantically", "where is this handled", or when exact grep is not enough.
allowed-tools: Bash, Read
---

# Semantic grep workflow (ogrep)

Fast semantic search over local repos using `ogrep` (SQLite index + OpenAI embeddings).

## Quick Start

```bash
# Index the repo (run once, or after major changes)
ogrep index .

# Semantic search (ALWAYS use --refresh for accurate results)
ogrep query "where is authentication handled?" -n 15 --refresh
```

## IMPORTANT: Always Use --refresh

**When querying, ALWAYS use the `--refresh` flag:**

```bash
ogrep query "your search" --refresh
```

The `--refresh` flag checks for changed files and reindexes them before searching.
Without it, queries may return stale results based on outdated embeddings.

This is especially critical in AI tool contexts where files are being edited
between queries. The `--refresh` operation is fast due to smart embedding reuse.

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
