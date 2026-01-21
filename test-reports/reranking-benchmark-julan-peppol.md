# OGREP Reranking Benchmark Report

**Repository:** julan_peppol (285 files, 1369 chunks)
**Date:** 2026-01-16
**ogrep version:** 0.8.0

## Latency Comparison (seconds per query)

| Model | Backend | Min | Max | Avg |
|-------|---------|-----|-----|-----|
| flashrank | FlashRank ONNX | 0.64 | 0.66 | **0.65** |
| flashrank:mini | FlashRank ONNX | 0.64 | 0.66 | **0.65** |
| minilm | sentence-transformers | 4.52 | 9.80 | 8.03 |
| bge-m3 | sentence-transformers | 4.53 | 4.55 | 4.54 |

## Test Queries

1. "where is authentication handled"
2. "how are invoices generated"
3. "peppol validation logic"

## Result Quality (top hit per query)

| Query | flashrank | bge-m3 |
|-------|-----------|--------|
| where is authentication handled | backend/src/api/auth/__init__.py | frontend/app/Http/Controllers/Auth/AuthenticatedSessionController.php |
| how are invoices generated | backend/src/api/services/billing_service.py | backend/src/engine/generator.py |
| peppol validation logic | backend/src/peppol/__init__.py | backend/src/peppol/providers/mock_file.py |

## Model Comparison

| Model | Size | Backend | Context | Parallel Safe | Locking |
|-------|------|---------|---------|---------------|---------|
| bge-m3 | 300MB | sentence-transformers | 8K | No | Required |
| minilm | 90MB | sentence-transformers | 512 | No | Required |
| flashrank | 4MB | ONNX | 512 | Yes | None |
| flashrank:mini | 50MB | ONNX | 512 | Yes | None |

## Key Findings

- **FlashRank is 7-12x faster** than sentence-transformers models
- **FlashRank models use ONNX runtime** - parallel-safe, no locking needed
- **No PyTorch overhead** - saves ~500MB memory per process
- **bge-m3** still provides best quality but requires locking for parallel use

## Recommendations

- **Parallel/concurrent use:** Use `flashrank` or `flashrank:mini` (no locking)
- **Best quality:** Use `bge-m3` (but requires locking)
- **Balance:** Use `flashrank:mini` (good quality, no locking, 50MB)

## Installation

```bash
# Lightweight (ONNX-based, parallel-safe)
pip install "ogrep[rerank-light]"

# Full (sentence-transformers, best quality)
pip install "ogrep[rerank]"

# Both backends
pip install "ogrep[rerank-all]"
```

## Usage

```bash
# Default (bge-m3)
ogrep query "auth" --rerank

# FlashRank (lightweight, parallel-safe)
ogrep query "auth" --rerank-model flashrank

# Set default via environment
export OGREP_RERANK_MODEL=flashrank
ogrep query "auth" --rerank
```
