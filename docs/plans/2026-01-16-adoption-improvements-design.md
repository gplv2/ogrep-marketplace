# ogrep Adoption Improvements Design

**Date:** 2026-01-16
**Status:** Draft
**Authors:** Glenn (architect), Claude (design partner)

## Executive Summary

Improve ogrep from 7/10 to 9/10 for AI tool integration by addressing trust and efficiency gaps identified in real-world testing.

**North Star Metric:** AI can confidently use ogrep results without retry loops or manual verification.

## Background

Claude Code evaluation of ogrep identified these gaps:

| Issue | Impact | User Quote |
|-------|--------|------------|
| Low confidence scores even for correct results | AI can't trust when to dig deeper | "Top result scored 0.37 despite being exactly right" |
| No file type filtering in queries | Wastes context window | "Couldn't say 'search only in templates/*.j2'" |
| Results can be overwhelming | Token inefficiency | "Complex queries return 15-20 chunks" |
| Confusing `-n` vs `--rerank-top` | Silent truncation | Undocumented interaction |

**What works well:** Semantic search (5/5), reranking (4/5), JSON output (5/5), index speed (4/5).

## Scope

### This Iteration

| Priority | Feature | Purpose |
|----------|---------|---------|
| P0 | Hybrid confidence scoring | AI knows when to trust results |
| P0 | Path filtering (`--glob`, `--exclude`) | Targeted queries, less noise |
| P1 | Summary mode (`--summarize`) | Token-efficient scanning |
| P1 | `-n` / `--rerank-top` clarification | Remove confusing interactions |

### Future Iteration (tracked separately)

| Feature | Notes |
|---------|-------|
| Query explanation (`--explain`) | Help AI understand why results matched |
| AST chunking as default | After performance validation |

### Final Step (after code complete)

- **Skill tuning:** Update marketplace plugin and Claude skill to leverage new flags
- Depends on all flags being finalized and docs updated

## Technical Design

### 1. Hybrid Confidence Scoring

**Problem:** Current relative scoring tells you "this is 90% as good as the best" but not "the best is actually good enough."

**Solution:** Combine relative position with absolute quality signals.

#### Output Schema

```json
{
  "rank": 1,
  "score": 0.37,
  "confidence": {
    "level": "high",
    "relative_pct": 100,
    "absolute_quality": "expected_range",
    "signal": "top_result_in_typical_range"
  }
}
```

#### Calculation Logic

```
1. Compute relative_pct = (score / top_score) * 100

2. Determine absolute_quality:
   - "strong"         if score >= 0.50 (top 10% of distribution)
   - "expected_range" if score >= 0.35 (typical good match)
   - "weak"           if score >= 0.25 (borderline)
   - "very_weak"      if score <  0.25

3. Combine into level:
   - "high"     = relative_pct >= 90% AND absolute_quality in (strong, expected_range)
   - "medium"   = relative_pct >= 75% OR absolute_quality == "expected_range"
   - "low"      = relative_pct >= 50% OR absolute_quality == "weak"
   - "very_low" = everything else

4. Generate human-readable signal:
   - "top_result_in_typical_range"
   - "close_to_top_but_weak_absolute"
   - "score_drop_from_top"
```

#### Calibration

Thresholds (0.50/0.35/0.25) will be calibrated per embedding model:
- OpenAI `text-embedding-3-small`
- Local `nomic-embed-text-v1.5`

Calibration data stored in `test-reports/confidence-calibration-*.md`.

---

### 2. Path Filtering (Hybrid Approach)

**Problem:** AI gets all results, has to mentally filter. Low `-n` with post-filter causes quality loss.

**Solution:** Use SQL pre-filter for simple patterns, over-fetch + fnmatch for complex patterns.

#### Pattern Classification

```
┌─────────────────┬──────────────────────────────────────┐
│ Simple          │ *.py, src/*, templates/*.j2          │
│ (SQL-capable)   │ No **, no multiple patterns          │
├─────────────────┼──────────────────────────────────────┤
│ Complex         │ **/*.py, src/**/*.j2                 │
│ (needs fnmatch) │ Multiple --glob flags                │
└─────────────────┴──────────────────────────────────────┘
```

#### Execution Flow

```
SIMPLE patterns → Pre-filter in SQL
┌─────────────────────────────────────────────────────────┐
│ SELECT c.*, f.path FROM chunks c                        │
│ JOIN files f ON c.file_id = f.id                        │
│ WHERE f.path GLOB '*.py'                                │
│ LIMIT top_k                                             │
└─────────────────────────────────────────────────────────┘

COMPLEX patterns → Over-fetch + post-filter
┌─────────────────────────────────────────────────────────┐
│ fetch_limit = top_k * 10                                │
│ hits = raw_query(fetch_limit)                           │
│ hits = [h for h in hits if fnmatch(h.path, pattern)]    │
│ return hits[:top_k]                                     │
└─────────────────────────────────────────────────────────┘
```

#### CLI

```bash
# Simple → SQL pre-filter
ogrep query "auth" --glob "*.py"
ogrep query "auth" --glob "src/*.php"

# Complex → over-fetch + fnmatch
ogrep query "auth" --glob "**/*.py"
ogrep query "auth" --glob "*.py" --glob "*.php"

# Exclude
ogrep query "auth" --exclude "tests/*"

# Combined
ogrep query "auth" --glob "*.py" --exclude "tests/*"
```

#### JSON Output

```json
{
  "query": "authentication",
  "filters": {
    "glob": ["*.py"],
    "exclude": null,
    "method": "sql_prefilter"
  },
  "filter_stats": {
    "candidates_before": 15,
    "candidates_after": 12,
    "removal_pct": 20
  },
  "warning": null,
  "results": [...]
}
```

#### Warning

If filter removes >50% of results:
```json
{
  "warning": "Filter removed 12 of 15 results. Consider increasing -n or broadening glob."
}
```

---

### 3. Summary Mode

**Problem:** 15-20 chunks flood the AI's context window. Often just needs to know *which files* matter.

**Solution:** `--summarize` flag returns file-level aggregation without chunk text.

#### CLI

```bash
ogrep query "authentication" --summarize
ogrep query "authentication" --summarize --glob "*.py" --rerank
```

#### Output Schema

```json
{
  "query": "authentication",
  "mode": "hybrid",
  "summary": true,
  "total_chunks_matched": 23,
  "files": [
    {
      "path": "src/auth/login.py",
      "relative_path": "src/auth/login.py",
      "chunks_matched": 4,
      "best_score": 0.47,
      "score_range": [0.35, 0.47],
      "confidence": "high",
      "lines_covered": [[12, 45], [78, 120], [145, 180], [200, 235]]
    }
  ],
  "search_time_ms": 145,
  "recommendation": "Use 'ogrep chunk <path>:<N>' to expand specific files"
}
```

#### Token Savings

| Output Type | Typical Size | Tokens (~4 chars/token) |
|-------------|--------------|-------------------------|
| Full (10 chunks) | ~8,000 chars | ~2,000 tokens |
| Summary (10 files) | ~1,200 chars | ~300 tokens |
| **Savings** | | **~85%** |

---

### 4. `-n` vs `--rerank-top` Clarification

**Problem:** Silent truncation when `-n > --rerank-top`.

**Solution:** Validation + clear error messages.

#### Semantics

| Flag | Meaning | Default |
|------|---------|---------|
| `-n` / `--top` | Final output count | 10 |
| `--rerank-top` | Rerank candidate pool size | 50 |

**Rule:** `--rerank-top` must be >= `-n`

#### Pipeline

```
1. FETCH: max(n, rerank_top) candidates from DB
2. RERANK: Score top rerank_top with cross-encoder
3. TRIM: Return top n from reranked results

VALID:
  -n 10 --rerank-top 50  → fetch 50, rerank 50, return 10 ✓

INVALID (now caught):
  -n 20 --rerank-top 15  → ERROR: rerank-top must be >= n
```

#### Error Output

```json
{
  "error": "--rerank-top (15) must be >= -n (20)",
  "error_code": "INVALID_RERANK_ARGS",
  "suggestion": "Use --rerank-top 20 or higher, or reduce -n to 15 or lower"
}
```

---

## Test Plan

### Test Environment

- **Codebase:** `/home/glenn/repos/julan_peppol` (Python/PHP/JS/YAML mix)
- **Backends:** OpenAI `text-embedding-3-small`, Local `nomic` via LM Studio

### Ground Truth Queries

| Query | Expected Area |
|-------|---------------|
| "Where are legacy invoices imported?" | Import/migration code |
| "How does frontend authenticate to backend?" | Auth flow, tokens |
| "How does export to CSV/JSON work?" | Export functionality |
| (more to discover during Phase 1) | |

### Test Isolation

**Critical:** Clean state between model tests.

```bash
# Files to remove between backend switches:
rm -f .ogrep/index.sqlite      # Main index
rm -f .ogrep/cache.sqlite      # Embedding cache (NEW)
rm -rf ~/.cache/ogrep/         # Global cache

# Or use: ogrep reset -f (should also remove cache.sqlite)
```

### Test Matrix

```
AXIS 1: Embedding Backend
├── OpenAI (text-embedding-3-small)
└── Local (nomic via LM Studio)

AXIS 2: Search Mode
├── semantic
├── fulltext
└── hybrid

AXIS 3: Reranking
├── without --rerank
└── with --rerank

AXIS 4: New Features
├── Hybrid confidence scoring
├── Path filtering (--glob, --exclude)
├── Summary mode (--summarize)
└── -n / --rerank-top validation

TOTAL: 2 × 3 × 2 = 12 base scenarios + feature-specific tests
```

### Success Criteria

| Feature | Metric | Target |
|---------|--------|--------|
| Confidence scoring | "high" confidence = actually correct | >90% precision |
| Path filtering | Correct files returned | 100% accuracy |
| Summary mode | Token reduction | >80% vs full output |
| Rerank validation | Invalid args caught | 100% |
| Regression | Existing tests pass | 100% |

---

## Implementation Order

### Phase 1: Foundation

- [ ] 1.1 Clean up reset command to also remove cache.sqlite
- [ ] 1.2 Verify model mismatch guards still work
- [ ] 1.3 Set up julan_peppol test environment
- [ ] 1.4 Discover ground-truth queries (with user input)

**Deliverable:** `test-reports/ground-truth-queries-julan-peppol.md`

### Phase 2: Confidence Scoring (P0)

- [ ] 2.1 Implement hybrid confidence model in search.py
- [ ] 2.2 Update JSON output schema
- [ ] 2.3 Calibrate thresholds on OpenAI backend
- [ ] 2.4 Calibrate thresholds on Nomic backend
- [ ] 2.5 Add unit tests for confidence calculation

**Deliverable:** `test-reports/confidence-calibration-*.md`

### Phase 3: Path Filtering (P0)

- [ ] 3.1 Add --glob and --exclude args to CLI
- [ ] 3.2 Implement pattern classifier (simple vs complex)
- [ ] 3.3 Implement SQL pre-filter for simple patterns
- [ ] 3.4 Implement over-fetch + fnmatch for complex patterns
- [ ] 3.5 Add filter stats and warning to JSON output
- [ ] 3.6 Add unit tests for path filtering

**Deliverable:** `test-reports/path-filtering-validation-*.md`

### Phase 4: Result Limiting (P1)

- [ ] 4.1 Implement --summarize mode
- [ ] 4.2 Add file-level aggregation logic
- [ ] 4.3 Measure token savings
- [ ] 4.4 Add validation for -n vs --rerank-top
- [ ] 4.5 Update CLI help text
- [ ] 4.6 Add unit tests

**Deliverable:** `test-reports/summary-mode-token-savings-*.md`

### Phase 5: Integration Testing

- [ ] 5.1 Full test matrix on OpenAI backend
- [ ] 5.2 Full test matrix on Nomic backend
- [ ] 5.3 Regression: run existing test suite
- [ ] 5.4 Document model-specific behavior differences

**Deliverable:** `test-reports/integration-test-results-*.md`

### Phase 6: Documentation

- [ ] 6.1 Update CLAUDE.md with new flags
- [ ] 6.2 Update README.md
- [ ] 6.3 Update CLI --help text
- [ ] 6.4 Add CHANGELOG.md entry
- [ ] 6.5 Bump version numbers (all locations)

### Phase 7: Skill Tuning (FINAL)

**NOTE:** This phase requires interactive Q/A. User has studied skill design
extensively and has specific intentions for how skills/commands should work.
Do not auto-implement; instead gather requirements through discussion.

- [ ] 7.1 Q/A session: Understand user's vision for skill updates
- [ ] 7.2 Update plugins/ogrep/skills/SKILL.md based on discussion
- [ ] 7.3 Update plugins/ogrep/commands/ slash commands based on discussion
- [ ] 7.4 Test skill integration with Claude Code
- [ ] 7.5 Update marketplace plugin.json if needed

---

## Dependency Graph

```
Phase 1 (Foundation)
    │
    ├──→ Phase 2 (Confidence) ──→ Phase 5 (Integration)
    │                                   │
    ├──→ Phase 3 (Filtering) ───────────┤
    │                                   │
    └──→ Phase 4 (Summarize) ───────────┘
                                        │
                                        ▼
                                  Phase 6 (Docs)
                                        │
                                        ▼
                                  Phase 7 (Skill)
```

---

## Documentation Policy

- Docs updated with each feature merge
- Version numbers kept in sync across all locations:
  - `pyproject.toml`
  - `ogrep/__init__.py`
  - `ogrep/cli.py`
  - `plugins/ogrep/.claude-plugin/plugin.json`
  - `.claude-plugin/marketplace.json`
  - `CHANGELOG.md`
- Test reports stored in `test-reports/`

---

## Future Work (Not in This RFC)

| Feature | Description | Dependency |
|---------|-------------|------------|
| Query explanation (`--explain`) | Show why results matched, embedding breakdown | After confidence calibration |
| AST chunking as default | Make `--ast` the default mode | After performance validation |

---

## Appendix: Files Modified

| Phase | Files |
|-------|-------|
| 1 | `ogrep/commands/reset.py` |
| 2 | `ogrep/search.py`, `ogrep/commands/query.py` |
| 3 | `ogrep/search.py`, `ogrep/commands/query.py`, `ogrep/cli.py` |
| 4 | `ogrep/commands/query.py`, `ogrep/cli.py` |
| 5 | Test files only |
| 6 | `CLAUDE.md`, `README.md`, `CHANGELOG.md` |
| 7 | `plugins/ogrep/skills/*`, `plugins/ogrep/commands/*` |
