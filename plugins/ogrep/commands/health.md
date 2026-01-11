---
description: Show database health diagnostics and repair options
allowed-tools: Bash
argument-hint: [--vacuum] [--rebuild-fts] [--integrity] [--full]
---

Display comprehensive database diagnostics including table sizes, indexes, SQLite info, FTS5 stats, and integrity checks.

**Diagnostic (default):**
- `ogrep health` - Full diagnostic output

**Repair options:**
- `ogrep health --vacuum` - Reclaim space and defragment
- `ogrep health --rebuild-fts` - Drop and rebuild FTS5 index
- `ogrep health --integrity` - Run full integrity check (slow)
- `ogrep health --full` - Vacuum + rebuild-fts + integrity
