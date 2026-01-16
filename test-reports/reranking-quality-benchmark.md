# Reranking Quality Benchmark

**Date:** 2026-01-16
**Codebase:** julan_peppol
**Queries:** 10
**Embedding Model:** text-embedding-3-small (OpenAI)

## Summary

| Model | Hit@1 | Hit@3 | Hit@5 | MRR |
|-------|-------|-------|-------|-----|
| baseline | 6/10 | 8/10 | 8/10 | 0.700 |
| flashrank | 5/10 | 6/10 | 6/10 | 0.550 |
| flashrank:mini | 4/10 | 5/10 | 7/10 | 0.478 |
| voyage | 5/10 | 6/10 | 7/10 | 0.599 |
| voyage:lite | 3/10 | 5/10 | 8/10 | 0.458 |
| minilm | 5/10 | 6/10 | 8/10 | 0.617 |

**Winner:** baseline (MRR 0.700)

---

## Per-Query Results

### Query 1: "where are legacy invoices imported"

**Expected:** `backend/src/ledger/legacy.py`
**Category:** Import/export

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 5 | Yes |
| voyage | 2 | Yes |
| voyage:lite | 5 | Yes |
| minilm | 2 | Yes |

### Query 2: "how does frontend authenticate to backend"

**Expected:** `frontend/tests/Feature/Auth/ApiAuthenticationTest.php`
**Category:** Authentication

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | - | No |
| flashrank:mini | - | No |
| voyage | 4 | Yes |
| voyage:lite | 5 | Yes |
| minilm | 6 | Yes |

### Query 3: "export to CSV JSON"

**Expected:** `frontend/resources/js/Components/TableExport.vue`
**Category:** Import/export

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | - | No |
| flashrank:mini | 3 | Yes |
| voyage | 1 | Yes |
| voyage:lite | 1 | Yes |
| minilm | 1 | Yes |

### Query 4: "VAT calculation"

**Expected:** `backend/src/models/account.py`
**Category:** Business logic

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | 2 | Yes |
| flashrank:mini | 4 | Yes |
| voyage | 8 | Yes |
| voyage:lite | 5 | Yes |
| minilm | 4 | Yes |

### Query 5: "database connection pool"

**Expected:** `backend/src/db/connection.py`
**Category:** Infrastructure

| Model | Rank | Found |
|-------|------|-------|
| baseline | 2 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 1 | Yes |
| voyage | 1 | Yes |
| voyage:lite | 3 | Yes |
| minilm | 1 | Yes |

### Query 6: "invoice list API endpoint"

**Expected:** `backend/src/api/routers/invoices.py`
**Category:** API endpoints

| Model | Rank | Found |
|-------|------|-------|
| baseline | - | No |
| flashrank | - | No |
| flashrank:mini | - | No |
| voyage | 1 | Yes |
| voyage:lite | 3 | Yes |
| minilm | - | No |

### Query 7: "payment status workflow"

**Expected:** `backend/src/ledger/payment_status.py`
**Category:** Payment/billing

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 1 | Yes |
| voyage | - | No |
| voyage:lite | 7 | Yes |
| minilm | 1 | Yes |

### Query 8: "how are billing runs created"

**Expected:** `backend/src/ledger/billing_runs.py`
**Category:** Payment/billing

| Model | Rank | Found |
|-------|------|-------|
| baseline | 2 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 1 | Yes |
| voyage | 1 | Yes |
| voyage:lite | 1 | Yes |
| minilm | 1 | Yes |

### Query 9: "API error response handling"

**Expected:** `backend/src/api/middleware.py`
**Category:** Error handling

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 1 | Yes |
| voyage | 9 | Yes |
| voyage:lite | 6 | Yes |
| minilm | 1 | Yes |

### Query 10: "BillingApiException"

**Expected:** `frontend/app/Services/BillingApiException.php`
**Category:** Error handling

| Model | Rank | Found |
|-------|------|-------|
| baseline | - | No |
| flashrank | - | No |
| flashrank:mini | - | No |
| voyage | 1 | Yes |
| voyage:lite | 1 | Yes |
| minilm | 4 | Yes |

---

## Metrics Explanation

- **Hit@K**: Expected file appears in top K results
- **MRR**: Mean Reciprocal Rank = average of 1/rank for each query
  - MRR 1.0 = all queries have correct file at rank 1
  - MRR 0.5 = average rank is 2

## Key Insights

1. **Baseline wins**: OpenAI text-embedding-3-small without reranking achieves the best MRR (0.700)
2. **Voyage finds unique matches**: Query 6 ("invoice list API endpoint") and Query 10 ("BillingApiException") are only found by Voyage models
3. **Reranking can hurt**: flashrank loses Query 2 and Query 3 that baseline found
4. **Trade-offs exist**: Different models excel at different query types
