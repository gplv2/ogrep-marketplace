# Reranking vs OpenAI Baseline Comparison

**Date:** 2026-01-17 13:04
**Best Reranking Model:** minilm
**Baseline:** OpenAI semantic search (no reranking)

## Summary

| Metric | Baseline | Best Reranker | Improvement |
|--------|----------|---------------|-------------|
| HIT@AT@1 | 5/10 | 5/10 | 0 |
| HIT@AT@3 | 6/10 | 8/10 | +2 |
| HIT@AT@5 | 8/10 | 9/10 | +1 |
| MRR | 0.617 | 0.673 | +0.056 |

---

## Per-Query Position Changes

| # | Query | Baseline Rank | Reranked Rank | Lift |
|---|-------|---------------|---------------|------|
| 1 | where are legacy invoices imported | 1 | 2 | -1 |
| 2 | how does frontend authenticate to b... | 1 | 7 | -6 |
| 3 | export to CSV JSON | 1 | 1 | 0 |
| 4 | VAT calculation | 4 | 2 | +2 |
| 5 | database connection pool | 4 | 1 | +3 |
| 6 | invoice list API endpoint | 6 | 4 | +2 |
| 7 | payment status workflow | 1 | 1 | 0 |
| 8 | how are billing runs created | 2 | 1 | +1 |
| 9 | API error response handling | 1 | 1 | 0 |
| 10 | BillingApiException | - | 3 | NEW |

---

## Lift Analysis

- **Improved:** 5/10 queries
- **Unchanged:** 3/10 queries
- **Degraded:** 2/10 queries
- **Total position lift:** 1 positions

---

## Recommendation

**Strong recommendation to use minilm reranking.** MRR improved by 0.056 (5.6%).
