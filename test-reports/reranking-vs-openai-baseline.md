# Reranking vs OpenAI Baseline Comparison

**Date:** 2026-01-16
**Best Reranking Model:** minilm (MRR 0.617)
**Baseline:** OpenAI text-embedding-3-small (no reranking)

## Summary

| Metric | Baseline | Best Reranker | Improvement |
|--------|----------|---------------|-------------|
| HIT@1 | 6/10 | 5/10 | -1 |
| HIT@3 | 8/10 | 6/10 | -2 |
| HIT@5 | 8/10 | 8/10 | 0 |
| MRR | 0.700 | 0.617 | -0.083 |

---

## Per-Query Position Changes

| # | Query | Baseline Rank | Reranked Rank | Lift |
|---|-------|---------------|---------------|------|
| 1 | where are legacy invoices imported... | 1 | 2 | -1 |
| 2 | how does frontend authenticate to... | 1 | 6 | -5 |
| 3 | export to CSV JSON | 1 | 1 | 0 |
| 4 | VAT calculation | 1 | 4 | -3 |
| 5 | database connection pool | 2 | 1 | +1 |
| 6 | invoice list API endpoint | - | - | - |
| 7 | payment status workflow | 1 | 1 | 0 |
| 8 | how are billing runs created | 2 | 1 | +1 |
| 9 | API error response handling | 1 | 1 | 0 |
| 10 | BillingApiException | - | 4 | NEW |

---

## Lift Analysis

- **Improved:** 3/10 queries
- **Unchanged:** 3/10 queries
- **Degraded:** 4/10 queries
- **Total position lift:** -7 positions

---

## All Models Comparison

| Model | Hit@1 | MRR | vs Baseline |
|-------|-------|-----|-------------|
| **baseline** | 6/10 | 0.700 | - |
| minilm | 5/10 | 0.617 | -0.083 |
| voyage | 5/10 | 0.599 | -0.101 |
| flashrank | 5/10 | 0.550 | -0.150 |
| flashrank:mini | 4/10 | 0.478 | -0.222 |
| voyage:lite | 3/10 | 0.458 | -0.242 |

---

## Voyage AI Analysis

Voyage reranking (rerank-2.5) showed mixed results:

**Strengths:**
- Found "invoice list API endpoint" (Query 6) at rank 1 - baseline missed this
- Found "BillingApiException" (Query 10) at rank 1 - baseline missed this

**Weaknesses:**
- Pushed "VAT calculation" from rank 1 to rank 8
- Pushed "API error response handling" from rank 1 to rank 9
- Lost "payment status workflow" entirely

**Verdict:** Voyage reranking trades some reliable matches for finding harder queries. May be useful as a fallback when baseline returns poor results.

---

## Recommendation

**Reranking does not improve results** for this codebase with OpenAI embeddings. The baseline semantic search achieves MRR 0.700, which is already excellent.

**When to use reranking:**
1. When using lower-quality embeddings (local models)
2. When queries consistently return poor top results
3. When searching across very large codebases where initial retrieval has more noise

**For julan_peppol:** Stick with baseline (no reranking) for best results.
