# ogrep v0.4.5 Release Notes

## What's New

### Preview Before You Index

Ever wondered what files ogrep will actually index? Now you can see exactly what's happening before committing:

```bash
ogrep index . --list
```

You'll see files grouped by extension, sorted by size, with binary files clearly marked:

```
── .py (34 files, 179.6KB) ──
      101B  ogrep/__main__.py
    17.0KB  ogrep/commands/benchmark.py

── (no extension) (3 files, 45.2KB) ──
  [BINARY: application/x-sqlite3]   12.0KB  data
      25.2KB  Makefile

──────────────────────────────────────────────────
Would index: 35 files, 180.4KB
Excluded by detection: 1 files, 12.0KB
```

Plus helpful extras:
- **Top 10 directories** by file count - see where your code lives
- **Largest indexable files** - spot potential problems
- **Review suggestions** - flags logs, dumps, and other files that might distort search results

### Smarter Binary Detection

ogrep now uses the system `file` command for accurate MIME-type detection. This catches:

- SQLite databases without `.sqlite` extension
- Binary files masquerading as text
- Data files that slip through extension filtering

Works automatically. Use `--no-detect` if you need faster scans without MIME checking.

### Persistent Exclusions with .ogrepignore

Tired of passing `-e` flags every time? Create a `.ogrepignore` file in your repo:

```bash
# .ogrepignore
*.sql
migrations/*
legacy/*
*.generated.ts
```

Patterns use glob syntax like `.gitignore`. Loaded automatically on every index operation.

### Expanded Default Exclusions

More file types are excluded by default to keep your index focused on actual source code:

| Category | New Patterns |
|----------|--------------|
| Temp files | `*.tmp`, `*.temp` |
| Backups | `*.old`, `*.bak`, `*.backup`, `*.orig`, `*.swp`, `*~` |
| Data files | `*.csv`, `*.tsv`, `*.sqlt`, `*.dat`, `*.xml` |
| Database | `*.dump` |

### Cleaner File Handling

- **Empty files** (0 bytes) are now skipped automatically
- **Duplicate symlinks** pointing to the same file are deduplicated
- **Broken symlinks** are skipped gracefully
- **Version control directories** `.svn` and `.hg` (Mercurial) are now skipped alongside `.git`

## Upgrading

```bash
pip install --upgrade ogrep
# or
pip install --force-reinstall git+https://github.com/gplv2/ogrep.git
```

## Documentation

- [README.md](README.md) - Quick start and overview
- [LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md) - Detailed local model setup
- [CHANGELOG.md](CHANGELOG.md) - Full technical changelog

## Links

- GitHub: https://github.com/gplv2/ogrep-marketplace
