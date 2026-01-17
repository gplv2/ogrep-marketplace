# Reranking Quality Benchmark

**Date:** 2026-01-17 13:04
**Codebase:** julan_peppol
**Queries:** 10

## Summary

| Model | Hit@1 | Hit@3 | Hit@5 | MRR |
|-------|-------|-------|-------|-----|
| baseline | 5/10 | 6/10 | 8/10 | 0.617 |
| flashrank | 6/10 | 7/10 | 8/10 | 0.670 |
| flashrank:mini | 3/10 | 7/10 | 9/10 | 0.500 |
| voyage | 5/10 | 6/10 | 7/10 | 0.593 |
| voyage:lite | 5/10 | 5/10 | 5/10 | 0.564 |
| minilm | 5/10 | 8/10 | 9/10 | 0.673 |

**Winner:** minilm (MRR 0.673)

---

## Per-Query Results

### Query 1: "where are legacy invoices imported"

**Expected:** `backend/src/ledger/legacy.py`
**Category:** Import/export

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 4 | Yes |
| voyage | 2 | Yes |
| voyage:lite | 6 | Yes |
| minilm | 2 | Yes |

### Query 2: "how does frontend authenticate to backend"

**Expected:** `frontend/tests/Feature/Auth/ApiAuthenticationTest.php`
**Category:** Authentication

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | - | No |
| flashrank:mini | 4 | Yes |
| voyage | 5 | Yes |
| voyage:lite | 7 | Yes |
| minilm | 7 | Yes |

### Query 3: "export to CSV JSON"

**Expected:** `frontend/resources/js/Components/TableExport.vue`
**Category:** Import/export

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 3 | Yes |
| voyage | 1 | Yes |
| voyage:lite | 1 | Yes |
| minilm | 1 | Yes |

### Query 4: "VAT calculation"

**Expected:** `backend/src/models/account.py`
**Category:** Business logic

| Model | Rank | Found |
|-------|------|-------|
| baseline | 4 | Yes |
| flashrank | 2 | Yes |
| flashrank:mini | 3 | Yes |
| voyage | 10 | Yes |
| voyage:lite | 6 | Yes |
| minilm | 2 | Yes |

### Query 5: "database connection pool"

**Expected:** `backend/src/db/connection.py`
**Category:** Infrastructure

| Model | Rank | Found |
|-------|------|-------|
| baseline | 4 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 1 | Yes |
| voyage | 1 | Yes |
| voyage:lite | 1 | Yes |
| minilm | 1 | Yes |

### Query 6: "invoice list API endpoint"

**Expected:** `backend/src/api/routers/invoices.py`
**Category:** API endpoints

| Model | Rank | Found |
|-------|------|-------|
| baseline | 6 | Yes |
| flashrank | 5 | Yes |
| flashrank:mini | 3 | Yes |
| voyage | 1 | Yes |
| voyage:lite | 1 | Yes |
| minilm | 4 | Yes |

### Query 7: "payment status workflow"

**Expected:** `backend/src/ledger/payment_status.py`
**Category:** Payment/billing

| Model | Rank | Found |
|-------|------|-------|
| baseline | 1 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 1 | Yes |
| voyage | - | No |
| voyage:lite | - | No |
| minilm | 1 | Yes |

### Query 8: "how are billing runs created"

**Expected:** `backend/src/ledger/billing_runs.py`
**Category:** Payment/billing

| Model | Rank | Found |
|-------|------|-------|
| baseline | 2 | Yes |
| flashrank | 1 | Yes |
| flashrank:mini | 2 | Yes |
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
| voyage | 8 | Yes |
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
| minilm | 3 | Yes |

---

## Metrics Explanation

- **Hit@K**: Expected file appears in top K results
- **MRR**: Mean Reciprocal Rank = average of 1/rank for each query
  - MRR 1.0 = all queries have correct file at rank 1
  - MRR 0.5 = average rank is 2
