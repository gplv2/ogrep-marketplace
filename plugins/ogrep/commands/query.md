---
description: Run a semantic query over the local SQLite index and return top matches
allowed-tools: Bash
argument-hint: <query text>
---

Run:
- `ogrep query "$ARGUMENTS" --top 15 --refresh`

The `--refresh` flag ensures results reflect current code by checking for
changed files and reindexing them before querying. Always use it.

If it fails because the DB doesn't exist:
1) Run `/ogrep:index`
2) Retry the query.
