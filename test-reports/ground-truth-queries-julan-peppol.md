# Ground Truth Queries - julan_peppol

**Date:** 2026-01-16
**Codebase:** `/home/glenn/repos/julan_peppol`
**Backend:** OpenAI `text-embedding-3-small`
**Index Stats:** 285 files, 1369 chunks, 12.5 MB

## Purpose

This document establishes ground truth queries for calibrating confidence scoring.
All queries return correct results but with varying score ranges, demonstrating
the need for hybrid confidence scoring.

## Query Results Summary

| # | Query | Score Range | Confidence | Correct? | Issue |
|---|-------|-------------|------------|----------|-------|
| 1 | Legacy invoice import | 0.60-0.65 | all high | ✓ | None - scores high |
| 2 | Frontend auth to backend | 0.39-0.40 | all high | ✓ | Scores moderate but consistent |
| 3 | Export to CSV JSON | 0.02-0.03 | 1 high, 4 low | ✓ | **Scores very low despite correct results** |
| 4 | VAT calculation | 0.38-0.47 | 2 high, 3 med | ✓ | Score spread, mixed confidence |
| 5 | Database connection pool | 0.37-0.42 | 4 high, 1 med | ✓ | None - works well |

## Key Observation

**Query 3 ("export to CSV JSON")** demonstrates the exact problem:
- Top result is `TableExport.vue` - **exactly correct**
- Score is 0.0297 - appears "very weak"
- AI might distrust this result and enter a retry loop

This is the scenario the hybrid confidence scoring must solve.

---

## Detailed Query Results

### Query 1: "where are legacy invoices imported"

**Status:** Excellent results, high scores

| Rank | File | Score | Confidence |
|------|------|-------|------------|
| 1 | `backend/src/ledger/legacy.py:0` | 0.6551 | high |
| 2 | `backend/src/engine/legacy_importer.py:0` | 0.6277 | high |
| 3 | `backend/src/engine/legacy_importer.py:1` | 0.6167 | high |
| 4 | `backend/src/engine/legacy_importer.py:2` | 0.6137 | high |
| 5 | `backend/src/api/services/legacy_service.py:5` | 0.6051 | high |

**Analysis:** Scores in 0.60-0.65 range are "strong" in absolute terms. All results
are highly relevant. Current confidence scoring works correctly here.

---

### Query 2: "how does frontend authenticate to backend"

**Status:** Correct results, moderate scores

| Rank | File | Score | Confidence |
|------|------|-------|------------|
| 1 | `frontend/tests/Feature/Auth/ApiAuthenticationTest.php:2` | 0.3988 | high |
| 2 | `frontend/tests/Feature/Auth/ApiAuthenticationTest.php:0` | 0.3951 | high |
| 3 | `frontend/resources/js/Pages/Settings/Index.vue:0` | 0.3930 | high |
| 4 | `frontend/tests/Feature/Auth/ApiAuthenticationTest.php:3` | 0.3928 | high |
| 5 | `frontend/routes/auth.php:0` | 0.3917 | high |

**Analysis:** Scores cluster tightly around 0.39-0.40. All are marked "high"
because they're very close to the top score (relative scoring works). Results
are relevant - found auth tests, routes, and auth-related components.

---

### Query 3: "export to CSV JSON"

**Status:** PROBLEM CASE - Correct results, very low scores

| Rank | File | Score | Confidence |
|------|------|-------|------------|
| 1 | `frontend/resources/js/Components/TableExport.vue:0` | 0.0297 | high |
| 2 | `frontend/resources/js/Components/TableExport.vue:2` | 0.0164 | low |
| 3 | `frontend/resources/js/Components/TableExport.vue:1` | 0.0161 | low |
| 4 | `backend/src/export/__init__.py:0` | 0.0159 | low |
| 5 | `frontend/resources/js/Components/TableExport.vue:3` | 0.0156 | low |

**Analysis:**
- Top result `TableExport.vue` is **exactly the right file** (contains CSV/JSON export code)
- Score 0.0297 is very low in absolute terms
- Relative scoring marks only rank 1 as "high" (others drop below 75% threshold)
- **This is the exact scenario where AI would distrust correct results**

**Why scores are low:**
- Query is short/ambiguous ("export to CSV JSON")
- Vue template code has less semantic density than Python
- May benefit from fulltext FTS component in hybrid search

---

### Query 4: "VAT calculation"

**Status:** Good results, score spread

| Rank | File | Score | Confidence |
|------|------|-------|------------|
| 1 | `backend/src/models/account.py:1` | 0.4683 | high |
| 2 | `backend/src/engine/legacy_importer.py:5` | 0.4609 | high |
| 3 | `frontend/resources/js/Pages/Billing/Preview.vue:12` | 0.4189 | medium |
| 4 | `frontend/resources/js/Pages/Legacy/Index.vue:13` | 0.3842 | medium |
| 5 | `frontend/resources/js/Pages/Payments/Index.vue:9` | 0.3808 | medium |

**Analysis:** Good score range (0.38-0.47). Results are relevant - found VAT
number formatting, VAT calculation in legacy importer, and invoicing UI
components that display VAT amounts.

---

### Query 5: "database connection pool"

**Status:** Good results, good scores

| Rank | File | Score | Confidence |
|------|------|-------|------------|
| 1 | `frontend/config/database.php:1` | 0.4230 | high |
| 2 | `backend/src/db/connection.py:0` | 0.4182 | high |
| 3 | `backend/src/db/connection.py:1` | 0.4005 | high |
| 4 | `frontend/config/database.php:0` | 0.3915 | high |
| 5 | `backend/src/db/connection.py:2` | 0.3712 | medium |

**Analysis:** Scores in 0.37-0.42 range. Found both PHP (Laravel) and Python
database configuration/connection code. Results are highly relevant.

---

## Calibration Data for Hybrid Confidence

### Score Distribution (OpenAI text-embedding-3-small)

Based on these queries, observed score ranges:

| Quality | Score Range | Example |
|---------|-------------|---------|
| Strong match | 0.50-0.70 | "legacy invoices" → legacy.py |
| Good match | 0.35-0.50 | "VAT calculation" → account.py |
| Expected range | 0.30-0.40 | "database connection" → connection.py |
| Weak but correct | 0.20-0.30 | N/A in test set |
| Very weak | < 0.20 | "export CSV" → TableExport.vue |

### Recommended Absolute Thresholds

For OpenAI `text-embedding-3-small`:

```
strong:         >= 0.50  (top 10% of distribution)
expected_range: >= 0.35  (typical good match)
weak:           >= 0.25  (borderline)
very_weak:      <  0.25  (but may still be correct!)
```

### Special Case: Very Low Scores

Query 3 shows that scores below 0.10 can still return correct results.
The hybrid scoring should:

1. Flag these as "low_absolute_score" in the signal
2. BUT if it's rank 1 with significant gap to rank 2, acknowledge it's the best match
3. Include guidance: "Low absolute score but clear top result"

---

## Test Queries for Nomic Backend

These same queries should be run after reindexing with `nomic-embed-text-v1.5`
to calibrate thresholds for local models.

Expected differences:
- Nomic uses 768 dimensions vs 1536
- Score ranges may differ
- May need separate threshold tables per model

---

---

## Additional Queries (Added for Reranking Benchmark)

### Query 6: "invoice list API endpoint"

**Status:** Not found in top 10 for any model

| Rank | File | Score | Confidence |
|------|------|-------|------------|
| 1 | `frontend/app/Http/Controllers/InvoiceController.php:0` | ~0.35 | high |

**Analysis:** Expected `backend/src/api/routers/invoices.py` but getting the frontend
controller instead. The query is ambiguous - both are valid API endpoints for invoices.
May need more specific query like "FastAPI invoice router".

---

### Query 7: "payment status workflow"

**Status:** Excellent results

| Rank | File | Score | Confidence |
|------|------|-------|------------|
| 1 | `backend/src/ledger/payment_status.py:0` | ~0.55 | high |

**Analysis:** Direct match on expected file. Strong semantic alignment.

---

### Query 8: "how are billing runs created"

**Status:** Good results

| Rank | File | Score | Confidence |
|------|------|-------|------------|
| 1 | `backend/src/ledger/billing_runs.py:0` | ~0.50 | high |
| 2 | `backend/src/ledger/billing_runs.py:1` | ~0.48 | high |

**Analysis:** Multiple chunks from the expected file in top results. Strong match.

---

### Query 9: "API error response handling"

**Status:** Good results

| Rank | File | Score | Confidence |
|------|------|-------|------------|
| 1 | `backend/src/api/middleware.py:0` | ~0.45 | high |

**Analysis:** Found the middleware which handles API error responses. Correct result.

---

### Query 10: "BillingApiException"

**Status:** Mixed results across models

| Rank | File | Score | Confidence |
|------|------|-------|------------|
| 1 | `frontend/app/Http/Controllers/MappingController.php:0` | ~0.30 | medium |

**Analysis:** Expected `frontend/app/Services/BillingApiException.php` but baseline
semantic search doesn't find it. Notably, bge-m3 reranking finds it at rank 1,
while minilm finds it at rank 4. This is a case where reranking helps.

---

## Reranking Benchmark Results (2026-01-16)

The full benchmark comparing reranking models is available in:
- `reranking-quality-benchmark.md` - Detailed per-model, per-query results
- `reranking-vs-openai-baseline.md` - Comparison showing baseline outperforms rerankers

### Key Finding

**OpenAI semantic search (baseline) outperforms all reranking models on this query set.**

| Model | MRR | Hit@1 | Notes |
|-------|-----|-------|-------|
| baseline (no rerank) | 0.700 | 6/10 | **Winner** |
| bge-m3 | 0.650 | 6/10 | Best reranker, still worse than baseline |
| minilm | 0.617 | 5/10 | |
| flashrank | 0.550 | 5/10 | |
| flashrank:mini | 0.478 | 4/10 | |

### Why Reranking Hurts Performance

1. **Semantic embeddings already optimized:** OpenAI's text-embedding-3-small is
   well-calibrated for code search queries.

2. **Rerankers are MS-MARCO trained:** Cross-encoders like bge-m3 are trained on
   web search passages, not code. They may not understand code semantics well.

3. **Small candidate pool:** Reranking top 50 candidates from already-good results
   can't improve much but can shuffle incorrect results higher.

---

## Next Steps

1. Use this data to calibrate hybrid confidence thresholds (Phase 2)
2. Implement `absolute_quality` classification based on these ranges
3. Add `signal` field explaining the scoring decision
4. Test with Nomic backend after OpenAI implementation complete
5. Consider training or finding code-specific reranking models
