# Reranking vs OpenAI Baseline Comparison

**Date:** 2026-01-16 21:30
**Best Reranking Model:** flashrank
**Baseline:** OpenAI semantic search (no reranking)

## Summary

| Metric | Baseline | Best Reranker | Improvement |
|--------|----------|---------------|-------------|
| HIT@AT@1 | 4/10 | 6/10 | +2 |
| HIT@AT@3 | 6/10 | 7/10 | +1 |
| HIT@AT@5 | 8/10 | 7/10 | -1 |
| MRR | 0.545 | 0.633 | +0.088 |

---

## Per-Query Position Changes

| # | Query | Baseline Rank | Reranked Rank | Lift |
|---|-------|---------------|---------------|------|
| 1 | where are legacy invoices imported | 3 | 1 | +2 |
| 2 | how does frontend authenticate to b... | 1 | - | LOST |
| 3 | export to CSV JSON | 1 | 1 | 0 |
| 4 | VAT calculation | 5 | - | LOST |
| 5 | database connection pool | 4 | 1 | +3 |
| 6 | invoice list API endpoint | 6 | 3 | +3 |
| 7 | payment status workflow | 1 | 1 | 0 |
| 8 | how are billing runs created | 2 | 1 | +1 |
| 9 | API error response handling | 1 | 1 | 0 |
| 10 | BillingApiException | - | - | - |

---

## Lift Analysis

- **Improved:** 4/10 queries
- **Unchanged:** 4/10 queries
- **Degraded:** 2/10 queries
- **Total position lift:** 9 positions

---

## Recommendation

**Strong recommendation to use flashrank reranking.** MRR improved by 0.088 (8.8%).
