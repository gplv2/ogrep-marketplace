---
description: Force rebuild of the semantic search index from scratch
allowed-tools: Bash
argument-hint: [path]
---

Completely rebuild the index by removing it and reindexing from scratch.

Run:
- `ogrep reindex ${1:-.}`

This is equivalent to `ogrep reset --force && ogrep index`.
