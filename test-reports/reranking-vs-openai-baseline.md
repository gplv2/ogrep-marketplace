# Reranking vs OpenAI Baseline Comparison

**Date:** 2026-01-16 20:35
**Best Reranking Model:** bge-m3
**Baseline:** OpenAI semantic search (no reranking)

## Summary

| Metric | Baseline | Best Reranker | Improvement |
|--------|----------|---------------|-------------|
| HIT@1 | 6/10 | 6/10 | 0 |
| HIT@3 | 8/10 | 6/10 | -2 |
| HIT@5 | 8/10 | 8/10 | 0 |
| MRR | 0.700 | 0.650 | -0.050 |

---

## Per-Query Position Changes

| # | Query | Baseline Rank | Reranked Rank | Lift |
|---|-------|---------------|---------------|------|
| 1 | where are legacy invoices imported | 1 | 4 | -3 |
| 2 | how does frontend authenticate to b... | 1 | - | LOST |
| 3 | export to CSV JSON | 1 | 1 | 0 |
| 4 | VAT calculation | 1 | 4 | -3 |
| 5 | database connection pool | 2 | 1 | +1 |
| 6 | invoice list API endpoint | - | - | - |
| 7 | payment status workflow | 1 | 1 | 0 |
| 8 | how are billing runs created | 2 | 1 | +1 |
| 9 | API error response handling | 1 | 1 | 0 |
| 10 | BillingApiException | - | 1 | NEW |

---

## Lift Analysis

- **Improved:** 3/10 queries
- **Unchanged:** 4/10 queries
- **Degraded:** 3/10 queries
- **Total position lift:** -4 positions

---

## Recommendation

**Reranking does not improve results** for this query set. OpenAI semantic search is sufficient.
