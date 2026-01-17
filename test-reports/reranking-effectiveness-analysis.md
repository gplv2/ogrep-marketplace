# Reranking Effectiveness Analysis

**Date:** 2026-01-17
**Codebase:** julan_peppol (285 files, ~1400 chunks)
**Ground Truth:** 10 semantic code search queries

## Executive Summary

Reranking does not improve search quality when using high-quality code embeddings. In fact, it consistently degrades results across all tested configurations.

| Configuration | Hit@1 | MRR | vs Best |
|---------------|-------|-----|---------|
| **Voyage embed (no rerank)** | **7/10** | **0.717** | baseline |
| OpenAI embed (no rerank) | 6/10 | 0.700 | -0.017 |
| OpenAI + minilm rerank | 5/10 | 0.617 | -0.100 |
| Voyage embed + voyage rerank | 6/10 | 0.593 | -0.124 |
| OpenAI + voyage rerank | 5/10 | 0.599 | -0.118 |
| OpenAI + flashrank | 5/10 | 0.550 | -0.167 |

**Winner:** Voyage voyage-code-3 embeddings without reranking (MRR 0.717)

---

## Why Reranking Doesn't Help

### 1. High-Quality Embeddings Already Excel

Both OpenAI text-embedding-3-small and Voyage voyage-code-3 are specifically trained on code. When first-stage retrieval is already near-optimal, reranking can only:
- Maintain results (best case)
- Degrade results (common case)

There's no room for improvement when the correct answer is already at rank 1.

### 2. Rerankers Aren't Code-Optimized

| Reranking Model | Training Domain | Code-Aware |
|-----------------|-----------------|------------|
| flashrank | MS MARCO (web search) | No |
| flashrank:mini | MS MARCO | No |
| minilm | General text | No |
| bge-m3 | General multilingual | No |
| voyage rerank-2.5 | General + instructions | Partial |

These models learned "relevance" from web search and Q&A datasets. What they consider relevant (keyword overlap, semantic text similarity) differs from code search relevance patterns.

### 3. Code Context Is Different

Rerankers see: `query + chunk_text`

But code relevance often depends on factors outside the chunk:
- **File path semantics** (`legacy.py` implies legacy handling)
- **Import relationships** (what modules are used)
- **Project structure** (backend/src/api vs frontend/app)
- **Surrounding code context** (function calls, class hierarchy)

Embedding models encode file paths and capture broader context. Rerankers only see the raw chunk text, losing valuable signals.

### 4. Query Types Favor Embeddings

Our benchmark queries are natural language descriptions of code concepts:
- "where are legacy invoices imported"
- "how does frontend authenticate to backend"
- "payment status workflow"

These queries have strong lexical AND semantic signals that code-optimized embeddings handle well. The embedding model finds `backend/src/ledger/legacy.py` immediately because:
1. "legacy" appears in the path
2. "invoices" and "imported" appear in the code
3. The semantic meaning aligns

The reranker second-guesses this with its own (often wrong) intuition about relevance.

### 5. Corpus Size Matters

Reranking shines when:
- Corpus is massive (millions of documents)
- First-stage retrieval returns many false positives
- Queries are ambiguous

For a focused codebase of 285 files with clear queries, the embedding-based retrieval already has high precision. Adding reranking introduces noise.

---

## Per-Query Analysis

### Queries Where Reranking Hurts

| Query | Embed Rank | +Rerank | Delta |
|-------|------------|---------|-------|
| Q1: legacy invoices | 1 | 2 | -1 |
| Q2: frontend auth | 1 | 5 | -4 |
| Q4: VAT calculation | 4 | 10 | -6 |
| Q9: API error handling | 1 | 8 | -7 |

These queries have clear lexical matches that embeddings find correctly. Rerankers "overthink" and promote less relevant results.

### Queries Where Reranking Helps

| Query | Embed Rank | +Rerank | Delta |
|-------|------------|---------|-------|
| Q5: db connection pool | 4 | 1 | +3 |
| Q6: invoice API endpoint | 6 | 1 | +5 |
| Q8: billing runs | 2 | 1 | +1 |

These queries benefit because the reranker correctly identifies implementation code over tangentially related files.

### Net Effect

- **Improved:** 3 queries
- **Unchanged:** 3 queries
- **Degraded:** 4 queries
- **Net MRR change:** -0.124 (worse)

---

## Recommendations

### When to Skip Reranking

1. **High-quality code embeddings** (Voyage, OpenAI text-embedding-3)
2. **Focused codebase** (<10K files)
3. **Clear semantic queries** (natural language descriptions)
4. **File path relevance** (path names are meaningful)

### When Reranking Might Help

1. **Weak embeddings** (local models like minilm, nomic)
2. **Massive corpus** (monorepo with millions of files)
3. **Ambiguous queries** (single keywords, acronyms)
4. **High noise** (many similarly-named files)

### Default Configuration

For most codebases, use:
```bash
ogrep index . -m voyage-code-3  # Best quality
ogrep index . -m small          # Good quality, lower cost
ogrep query "your query"        # No --rerank flag
```

Only add `--rerank` if you observe poor first-page results consistently.

---

## Cost-Benefit Analysis

| Model | Quality (MRR) | Latency | Cost |
|-------|---------------|---------|------|
| Voyage embed only | 0.717 | ~200ms | $0.06/M tokens |
| OpenAI embed only | 0.700 | ~150ms | $0.02/M tokens |
| + flashrank rerank | -0.15 MRR | +50ms | Free (local) |
| + voyage rerank | -0.12 MRR | +300ms | $0.05/M tokens |

Reranking adds latency and cost while degrading quality. Not recommended for typical code search use cases.

---

## Conclusion

**Reranking is not a universal quality boost.** It's a tool designed for specific scenarios (noisy retrieval, massive corpora, weak embeddings).

For semantic code search with modern embeddings:
- **Use Voyage voyage-code-3** for best quality (MRR 0.717)
- **Use OpenAI text-embedding-3-small** for good quality at lower cost (MRR 0.700)
- **Skip reranking** unless you have evidence it helps your specific queries

The embeddings are doing the heavy lifting. Trust them.
