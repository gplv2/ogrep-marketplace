# ogrep Quality & Performance Benchmark Report

**Date:** 2026-01-16
**Version:** 0.8.0
**Codebase tested:** julan_peppol (285 files, PHP + Python mixed)
**Author:** Automated benchmark via quality_benchmark.py

---

## Executive Summary

This report documents comprehensive quality and performance testing of ogrep's semantic search capabilities, comparing:
1. **Embedding models:** OpenAI vs Nomic (local)
2. **Reranking models:** flashrank, flashrank:mini, minilm, bge-m3
3. **Search quality:** MRR, Hit@1, Hit@3, Hit@5 metrics

### Key Findings

| Configuration | MRR | Hit@1 | Index Time | Cost |
|--------------|-----|-------|------------|------|
| **OpenAI (no rerank)** | **0.700** | 6/10 | 30s | ~$0.02 |
| OpenAI + bge-m3 | 0.650 | 6/10 | 30s | ~$0.02 |
| **Nomic + flashrank** | **0.633** | 6/10 | 17min | $0.00 |
| Nomic (no rerank) | 0.545 | 4/10 | 17min | $0.00 |

**Winner:** OpenAI without reranking (MRR 0.700)
**Best Local:** Nomic with flashrank reranking (MRR 0.633)

---

## Test Methodology

### Ground Truth Queries

10 queries with known expected file paths:

| # | Query | Expected File | Category |
|---|-------|---------------|----------|
| 1 | "where are legacy invoices imported" | backend/src/ledger/legacy.py | Import/export |
| 2 | "how does frontend authenticate to backend" | frontend/tests/Feature/Auth/ApiAuthenticationTest.php | Authentication |
| 3 | "export to CSV JSON" | frontend/resources/js/Components/TableExport.vue | Import/export |
| 4 | "VAT calculation" | backend/src/models/account.py | Business logic |
| 5 | "database connection pool" | backend/src/db/connection.py | Infrastructure |
| 6 | "invoice list API endpoint" | backend/src/api/routers/invoices.py | API endpoints |
| 7 | "payment status workflow" | backend/src/ledger/payment_status.py | Payment/billing |
| 8 | "how are billing runs created" | backend/src/ledger/billing_runs.py | Payment/billing |
| 9 | "API error response handling" | backend/src/api/middleware.py | Error handling |
| 10 | "BillingApiException" | frontend/app/Services/BillingApiException.php | Error handling |

### Metrics

- **Hit@K:** Expected file appears in top K results
- **MRR:** Mean Reciprocal Rank = average of 1/rank
  - MRR 1.0 = perfect (all at rank 1)
  - MRR 0.5 = average rank 2

### Test Environment

- **Hardware:** Linux x86_64, CPU-only (no GPU)
- **Python:** 3.12.8
- **ogrep:** 0.8.0
- **LM Studio:** For local Nomic embeddings
- **Reranking backends:** sentence-transformers 5.2.0, flashrank 0.2.10

---

## Detailed Results

### OpenAI Embedding Results

**Model:** text-embedding-3-small (1536 dimensions)

| Reranker | Hit@1 | Hit@3 | Hit@5 | MRR |
|----------|-------|-------|-------|-----|
| **None (baseline)** | **6/10** | **8/10** | **8/10** | **0.700** |
| bge-m3 | 6/10 | 6/10 | 8/10 | 0.650 |
| minilm | 5/10 | 6/10 | 8/10 | 0.617 |
| flashrank | 5/10 | 6/10 | 6/10 | 0.550 |
| flashrank:mini | 4/10 | 5/10 | 7/10 | 0.478 |

**Analysis:**
- Reranking HURTS performance with OpenAI embeddings
- OpenAI embeddings are already well-calibrated for code search
- Cross-encoder rerankers (trained on MS-MARCO web passages) don't improve code understanding

### Nomic Embedding Results

**Model:** nomic-embed-text-v1.5 (768 dimensions)

| Reranker | Hit@1 | Hit@3 | Hit@5 | MRR |
|----------|-------|-------|-------|-----|
| **flashrank** | **6/10** | **7/10** | 7/10 | **0.633** |
| minilm | 4/10 | 7/10 | 8/10 | 0.568 |
| None (baseline) | 4/10 | 6/10 | 8/10 | 0.545 |
| bge-m3 | 3/10 | 7/10 | 7/10 | 0.516 |
| flashrank:mini | 4/10 | 6/10 | 6/10 | 0.512 |

**Analysis:**
- Reranking HELPS with Nomic embeddings (+16% MRR)
- flashrank provides best improvement (lightweight, fast)
- bge-m3 is too slow for practical use (~30s/query on CPU)

---

## Per-Query Analysis

### Query 1: "where are legacy invoices imported"
- **OpenAI:** rank 1 (baseline)
- **Nomic:** rank 3 (baseline), rank 1 (flashrank)
- **Note:** Reranking helps Nomic find correct file

### Query 2: "how does frontend authenticate to backend"
- **OpenAI:** rank 1 (baseline)
- **Nomic:** rank 1 (baseline), NOT FOUND with reranking
- **Note:** Counterintuitive - reranking hurts on this query

### Query 3: "export to CSV JSON"
- **Both:** rank 1 across all configs
- **Note:** Easy query, all models succeed

### Query 4: "VAT calculation"
- **OpenAI:** rank 1 (baseline)
- **Nomic:** rank 5 (baseline), NOT FOUND with flashrank
- **Note:** Nomic struggles with business logic queries

### Query 5: "database connection pool"
- **OpenAI:** rank 2 (baseline), rank 1 (with rerank)
- **Nomic:** rank 4 (baseline), rank 1 (with rerank)
- **Note:** Both benefit from reranking on this query

### Query 6: "invoice list API endpoint"
- **OpenAI:** NOT FOUND (ambiguous query)
- **Nomic:** rank 6 (baseline), rank 2-3 (with rerank)
- **Note:** Nomic actually outperforms OpenAI here

### Query 7: "payment status workflow"
- **Both:** rank 1 across most configs
- **Note:** Easy query with strong keyword match

### Query 8: "how are billing runs created"
- **OpenAI:** rank 2 (baseline), rank 1 (with rerank)
- **Nomic:** rank 2 (baseline), rank 1 (with rerank)
- **Note:** Similar behavior, slight benefit from reranking

### Query 9: "API error response handling"
- **Both:** rank 1 across all configs
- **Note:** Easy query

### Query 10: "BillingApiException"
- **OpenAI:** NOT FOUND (baseline), rank 1 (bge-m3)
- **Nomic:** NOT FOUND (baseline), rank 1 (bge-m3)
- **Note:** Exact class name search benefits from cross-encoder

---

## Performance Benchmarks

### Indexing Performance

| Embedding | Files | Chunks | Time | Throughput |
|-----------|-------|--------|------|------------|
| OpenAI | 285 | 1,369 | 30s | 9.5 files/s |
| Nomic | 285 | 4,090 | 17min | 0.28 files/s |

**Note:** Nomic creates more chunks due to smaller default chunk size.

### Query Performance

| Reranker | Avg Query Time |
|----------|----------------|
| None | <100ms |
| flashrank | ~200ms |
| flashrank:mini | ~300ms |
| minilm | ~2s |
| bge-m3 | ~30s |

**Note:** On CPU without GPU. Times would be much faster with CUDA.

---

## Recommendations

### For Production (Quality Priority)

```bash
# Use OpenAI, no reranking
export OPENAI_API_KEY=your_key
ogrep index .
ogrep query "your search"
```

### For Privacy/Offline (Local Priority)

```bash
# Use Nomic + flashrank
lms server start
lms load nomic-embed-text-v1.5 -y
export OGREP_BASE_URL=http://localhost:1234/v1
export OGREP_MODEL=nomic
ogrep index .
ogrep query "your search" --rerank --rerank-model flashrank
```

### Decision Matrix

| Requirement | Recommended Setup |
|-------------|-------------------|
| Maximum accuracy | OpenAI (no rerank) |
| Privacy/compliance | Nomic + flashrank |
| Offline capability | Nomic + flashrank |
| Minimum cost | Nomic + flashrank |
| Fastest indexing | OpenAI |
| Fastest queries | Any (no rerank) |

---

## Conclusions

1. **OpenAI embeddings are best** for code search quality (0.700 MRR)

2. **Reranking behavior differs by embedding quality:**
   - Strong embeddings (OpenAI): reranking hurts
   - Weaker embeddings (Nomic): reranking helps

3. **Local is viable** with 10% quality trade-off:
   - Nomic + flashrank achieves 0.633 MRR
   - Zero cost, full privacy, offline capable

4. **flashrank is the best reranker** for local use:
   - Lightweight (4MB ONNX model)
   - Parallel-safe (no locking needed)
   - Fast (~200ms/query)

5. **bge-m3 is impractical** on CPU:
   - ~30s per query
   - Best quality reranker but too slow

---

## Future Work

- [ ] Test with GPU acceleration (bge-m3 may become viable)
- [ ] Benchmark other local models (MiniLM, BGE-base)
- [ ] Test code-specific rerankers (if available)
- [ ] Larger ground truth set (100+ queries)
- [ ] Cross-repository validation

---

## Appendix: Benchmark Script

Location: `scripts/quality_benchmark.py`

```bash
# Run benchmark
python scripts/quality_benchmark.py --repo /path/to/repo --verbose

# Output reports to custom directory
python scripts/quality_benchmark.py --output-dir ./reports
```

---

*Report generated by ogrep quality benchmark suite*
