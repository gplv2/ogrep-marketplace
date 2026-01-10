---
description: Index the current repository for semantic search (creates .ogrep/index.sqlite)
allowed-tools: Bash
argument-hint: [path]
---

Run indexing with ogrep. If no path is provided, index the current directory.

Use:
- `ogrep index ${1:-.}`

If `ogrep` is not installed, tell the user to run:
- `pip install -e .` (from the repo root) OR `pip install ogrep` (if published later)

