# Reranking Quality Benchmark

**Date:** 2026-01-16 20:35
**Codebase:** julan_peppol
**Queries:** 10

## Summary

| Model | Hit@1 | Hit@3 | Hit@5 | MRR |
|-------|-------|-------|-------|-----|
| baseline | 6/10 | 8/10 | 8/10 | 0.700 |
| flashrank | 5/10 | 6/10 | 6/10 | 0.550 |
| flashrank:mini | 4/10 | 5/10 | 7/10 | 0.478 |
| minilm | 5/10 | 6/10 | 8/10 | 0.617 |
| bge-m3 | 6/10 | 6/10 | 8/10 | 0.650 |

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
| minilm | 2 | Yes |
| bge-m3 | 4 | Yes |

### Query 2: "how does frontend authenticate to backend"

**Expected:** `frontend/tests/Feature/Auth/ApiAuthenticationTest.php`
**Category:** Authentication

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | - | No |
| flashrank:mini | - | No |
| minilm | 6 | Yes |
| bge-m3 | - | No |

### Query 3: "export to CSV JSON"

**Expected:** `frontend/resources/js/Components/TableExport.vue`
**Category:** Import/export

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | - | No |
| flashrank:mini | 3 | Yes |
| minilm | 1 | Yes |
| bge-m3 | 1 | Yes |

### Query 4: "VAT calculation"

**Expected:** `backend/src/models/account.py`
**Category:** Business logic

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | 2 | Yes |
| flashrank:mini | 4 | Yes |
| minilm | 4 | Yes |
| bge-m3 | 4 | Yes |

### Query 5: "database connection pool"

**Expected:** `backend/src/db/connection.py`
**Category:** Infrastructure

| Model | Rank | Found |
|-------|------|-------|
| baseline | 2 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 1 | Yes |
| minilm | 1 | Yes |
| bge-m3 | 1 | Yes |

### Query 6: "invoice list API endpoint"

**Expected:** `backend/src/api/routers/invoices.py`
**Category:** API endpoints

| Model | Rank | Found |
|-------|------|-------|
| baseline | - | No |
| flashrank | - | No |
| flashrank:mini | - | No |
| minilm | - | No |
| bge-m3 | - | No |

### Query 7: "payment status workflow"

**Expected:** `backend/src/ledger/payment_status.py`
**Category:** Payment/billing

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 1 | Yes |
| minilm | 1 | Yes |
| bge-m3 | 1 | Yes |

### Query 8: "how are billing runs created"

**Expected:** `backend/src/ledger/billing_runs.py`
**Category:** Payment/billing

| Model | Rank | Found |
|-------|------|-------|
| baseline | 2 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 1 | Yes |
| minilm | 1 | Yes |
| bge-m3 | 1 | Yes |

### Query 9: "API error response handling"

**Expected:** `backend/src/api/middleware.py`
**Category:** Error handling

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 1 | Yes |
| minilm | 1 | Yes |
| bge-m3 | 1 | Yes |

### Query 10: "BillingApiException"

**Expected:** `frontend/app/Services/BillingApiException.php`
**Category:** Error handling

| Model | Rank | Found |
|-------|------|-------|
| baseline | - | No |
| flashrank | - | No |
| flashrank:mini | - | No |
| minilm | 4 | Yes |
| bge-m3 | 1 | Yes |

---

## Metrics Explanation

- **Hit@K**: Expected file appears in top K results
- **MRR**: Mean Reciprocal Rank = average of 1/rank for each query
  - MRR 1.0 = all queries have correct file at rank 1
  - MRR 0.5 = average rank is 2
