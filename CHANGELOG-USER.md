# ogrep Updates — Recent Releases

*January 2026*

---

## March 21, 2026 — v0.8.9

### Leaner Skill, Faster Triggering

The ogrep skill definition is now 67% smaller, meaning less token overhead every time Claude uses it. Trigger accuracy is improved with clearer boundaries on when ogrep should (and shouldn't) be used.

### Removed: `refresh` Command

The standalone `refresh` command has been removed — it was just an alias for `ogrep index`. Use `ogrep query --refresh` to refresh before querying, or `ogrep index .` directly.

---

## January 26, 2026 — v0.8.8

### Bug Fix: Voyage AI Large Repository Indexing

Fixed an issue where indexing repositories with large files using Voyage AI would fail with "batch has X tokens after truncation" errors. The Voyage embedding path now properly respects the 120K token-per-batch API limit.

### Improved Error Messages

API errors now show clear, actionable messages instead of stack traces. Messages are context-aware—local embedding server errors show your `OGREP_BASE_URL` and suggest checking the server, while cloud API errors point to the relevant API key.

---

## January 22, 2026 — v0.8.6

### AST-Aware Auto-Tuning

The `ogrep tune` command now uses AST (Abstract Syntax Tree) chunking when tree-sitter is available. This means tuning respects semantic code boundaries like functions and classes, giving you more accurate optimal chunk size recommendations.

```bash
ogrep tune .  # Now uses AST chunking automatically
```

### Bug Fixes

- **Fixed tilde expansion**: The `OGREP_RERANK_LOCK` environment variable now properly expands `~` to your home directory

---

## January 16-21, 2026 — v0.8.0-0.8.5

### FlashRank Reranking (Parallel-Safe)

New lightweight reranking backend that works safely in parallel:

```bash
pip install "ogrep[rerank-light]"  # 4MB, no GPU needed
ogrep query "auth" --rerank
```

### Voyage AI Integration

Code-optimized embeddings and reranking from Voyage AI:

```bash
export VOYAGE_API_KEY=pa-...
ogrep index . -m voyage-code-3
ogrep query "auth" --rerank --rerank-model voyage
```

### Path Filtering

Filter results by file pattern:

```bash
ogrep query "auth" --glob "*.py"
ogrep query "auth" --exclude "tests/*"
```

### Summary Mode

Get file-level aggregation (85% fewer tokens):

```bash
ogrep query "auth" --summarize
```

---

## January 10-11, 2026 — v0.1.0-0.5.0

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
| **0.8.6** | Jan 22 | Tune command uses AST mode, tilde expansion fix |
| **0.8.5** | Jan 21 | PyPI re-release |
| **0.8.4** | Jan 21 | Smart API key detection, improved reporting |
| **0.8.3** | Jan 20 | FlashRank parallel safety, Voyage AI integration |
| **0.8.0** | Jan 16 | Path filtering, summary mode, reranking backends |
| **0.7.0** | Jan 14 | AST-aware chunking (default), branch-aware indexing |
| **0.6.4** | Jan 13 | Relative confidence scoring |
| **0.6.0** | Jan 12 | Full-text search, hybrid mode default |
| **0.5.0** | Jan 11 | Hybrid search, chunk navigation, confidence scoring |
| **0.4.5** | Jan 11 | File type detection, `.ogrepignore`, preview mode |
| **0.4.0** | Jan 11 | Local embedding models with LM Studio |
| **0.3.0** | Jan 10 | Smart embedding reuse, auto-tuning |
| **0.2.0** | Jan 10 | Configurable embedding models |
| **0.1.0** | Jan 10 | Initial release |

---

This changelog summarizes major releases. See [CHANGELOG.md](CHANGELOG.md) for detailed technical changes.
