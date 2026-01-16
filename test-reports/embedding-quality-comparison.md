# Embedding Quality Comparison: OpenAI vs Nomic

**Date:** 2026-01-16
**Codebase:** julan_peppol (285 files, PHP + Python)
**Ground Truth:** 10 queries with known expected files

## Executive Summary

| Embedding | Best Config | MRR | Hit@1 | Recommendation |
|-----------|-------------|-----|-------|----------------|
| **OpenAI text-embedding-3-small** | No reranking | **0.700** | 6/10 | Best quality |
| **Nomic embed-text-v1.5** | + flashrank | 0.633 | 6/10 | Best local/free |

**Key Finding:** OpenAI embeddings outperform Nomic by ~10% MRR on this benchmark.

---

## OpenAI Benchmark Results

**Model:** text-embedding-3-small (1536 dims)
**Index time:** ~30 seconds
**Cost:** ~$0.02

| Model | Hit@1 | Hit@3 | Hit@5 | MRR |
|-------|-------|-------|-------|-----|
| **baseline (no rerank)** | **6/10** | **8/10** | **8/10** | **0.700** |
| bge-m3 | 6/10 | 6/10 | 8/10 | 0.650 |
| minilm | 5/10 | 6/10 | 8/10 | 0.617 |
| flashrank | 5/10 | 6/10 | 6/10 | 0.550 |
| flashrank:mini | 4/10 | 5/10 | 7/10 | 0.478 |

**Observation:** Reranking HURTS performance with OpenAI embeddings. The embeddings are already well-calibrated.

---

## Nomic Benchmark Results

**Model:** nomic-embed-text-v1.5 (768 dims)
**Index time:** ~17 minutes
**Cost:** $0.00 (local)

| Model | Hit@1 | Hit@3 | Hit@5 | MRR |
|-------|-------|-------|-------|-----|
| **flashrank** | **6/10** | **7/10** | 7/10 | **0.633** |
| minilm | 4/10 | 7/10 | 8/10 | 0.568 |
| baseline (no rerank) | 4/10 | 6/10 | 8/10 | 0.545 |
| bge-m3 | 3/10 | 7/10 | 7/10 | 0.516 |
| flashrank:mini | 4/10 | 6/10 | 6/10 | 0.512 |

**Observation:** Reranking HELPS with Nomic embeddings (+16% MRR). The lightweight flashrank model provides the best improvement.

---

## Why Reranking Behavior Differs

### With OpenAI (reranking hurts):
- OpenAI embeddings are highly optimized for semantic similarity
- Rerankers (trained on MS-MARCO web passages) don't understand code as well
- Adding reranking introduces noise, shuffling correct results lower

### With Nomic (reranking helps):
- Local embeddings have less semantic precision
- Cross-encoder reranking adds a second opinion that improves ordering
- flashrank's lightweight model complements rather than conflicts

---

## Per-Query Comparison

| # | Query | OpenAI Best | Nomic Best |
|---|-------|-------------|------------|
| 1 | legacy invoices | rank 1 | rank 1 (flashrank) |
| 2 | frontend auth | rank 1 | rank 1 (baseline) |
| 3 | export CSV JSON | rank 1 | rank 1 (all) |
| 4 | VAT calculation | rank 1 | rank 5 (baseline) |
| 5 | database connection | rank 1 (flashrank) | rank 1 (flashrank) |
| 6 | invoice API | NOT FOUND | rank 2 (minilm) |
| 7 | payment status | rank 1 | rank 1 |
| 8 | billing runs | rank 1 (flashrank) | rank 1 (flashrank) |
| 9 | API error handling | rank 1 | rank 1 |
| 10 | BillingApiException | rank 1 (bge-m3) | rank 1 (bge-m3) |

---

## Recommendations

### For Maximum Quality:
```bash
# Use OpenAI embeddings, no reranking
export OPENAI_API_KEY=...
ogrep index .
ogrep query "your search"  # No --rerank flag
```

### For Privacy/Cost (Local):
```bash
# Use Nomic embeddings + flashrank reranking
export OGREP_BASE_URL=http://localhost:1234/v1
export OGREP_MODEL=nomic
ogrep index .
ogrep query "your search" --rerank --rerank-model flashrank
```

### Trade-off Summary:

| Factor | OpenAI | Nomic + flashrank |
|--------|--------|-------------------|
| Quality (MRR) | 0.700 | 0.633 (-9.5%) |
| Index time (285 files) | 30s | 17 min |
| Query time | <1s | <1s |
| Cost | ~$0.02 | $0.00 |
| Privacy | Cloud | Local |
| Offline capable | No | Yes |

---

## Methodology

- Ground truth: 10 queries with known correct file paths
- Metrics: Hit@K (file in top K), MRR (mean reciprocal rank)
- Reranking models tested: flashrank, flashrank:mini, minilm, bge-m3
- Index: 285 files, ~1400 chunks (OpenAI) / ~4000 chunks (Nomic)
