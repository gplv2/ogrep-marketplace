# ogrep Updates — Past 30 Days

*January 10-11, 2026*

## New Features

### Smarter Search with Hybrid Mode

Search now combines semantic understanding with keyword matching for more accurate results. Ask questions naturally, or search for exact function names — ogrep handles both.

```bash
ogrep query "how is authentication handled" --mode hybrid
```

### Confidence Scores

Results now show confidence levels (high, medium, low) so you know how much to trust each match. No more guessing if a result is actually relevant.

### Navigate Search Results with Context

Found something interesting? Expand the context around any result with the new chunk command:

```bash
ogrep chunk "src/auth.py:2" --context 1
```

### JSON Output for Automation

Query results can now be output as structured JSON, making it easy to integrate ogrep into scripts and AI tools:

```bash
ogrep query "error handling" --json
```

### File Type Detection

ogrep now uses your system's `file` command to accurately detect binary files, even ones with misleading extensions. Preview what will be indexed before committing:

```bash
ogrep index . --list
```

### Custom Exclusion Rules

Create a `.ogrepignore` file in your project root to permanently exclude files without passing flags every time:

```
# .ogrepignore
*.sql
migrations/*
legacy/*
```

### Run Completely Offline

Use local embedding models through LM Studio — no API keys, no cloud, no costs. Local models actually outperform cloud models on code search tasks.

```bash
export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index .
```

### Model Benchmarking

Compare embedding models to find the best one for your codebase:

```bash
ogrep benchmark . -s 10
```

---

## Improvements

- **Smarter file filtering**: Empty files, broken symlinks, and duplicate paths are automatically skipped
- **Better defaults**: Now excludes backup files (`.bak`, `.old`), temp files, data files (`.csv`, `.xml`), and database dumps
- **Version control aware**: Skips `.svn` and `.hg` directories alongside `.git`
- **Handles large repos**: File detection now processes in batches to handle repos with 30K+ files
- **Save 80% on API costs**: When re-indexing, ogrep reuses embeddings for unchanged code chunks
- **Auto-tuning**: Run `ogrep tune .` to find the optimal chunk size for your codebase

---

## Fixes

- **CI tests work without API keys**: Test suite no longer fails when `OPENAI_API_KEY` isn't set
- **Clear error messages**: Get helpful guidance when no embedding API is configured, instead of confusing output
- **PyPI installation fixed**: Removed invalid classifier that was blocking pip installs

---

## Versions Released

| Version | Date | Highlights |
|---------|------|------------|
| **0.5.0** | Jan 11 | Hybrid search, chunk navigation, confidence scoring |
| **0.4.5** | Jan 11 | File type detection, `.ogrepignore`, preview mode |
| **0.4.3** | Jan 11 | CI fixes |
| **0.4.2** | Jan 11 | Documentation improvements |
| **0.4.1** | Jan 11 | Smarter Claude Code integration, clear API errors |
| **0.4.0** | Jan 11 | Local embedding models with LM Studio |
| **0.3.4** | Jan 10 | Manual refresh command |
| **0.3.3** | Jan 10 | Auto-refresh before queries |
| **0.3.2** | Jan 10 | Code cleanup |
| **0.3.1** | Jan 10 | Expanded default exclusions |
| **0.3.0** | Jan 10 | Smart embedding reuse, auto-tuning |
| **0.2.0** | Jan 10 | Configurable embedding models |
| **0.1.0** | Jan 10 | Initial release |

---

This changelog summarizes 73 commits across 13 releases over the past 30 days. The project went from initial release to a mature semantic search tool with local model support, hybrid search, and comprehensive file filtering.
