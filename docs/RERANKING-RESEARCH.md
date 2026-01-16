# Reranking Research & Conclusions

**Date:** 2026-01-16
**Version:** ogrep 0.8.0
**Status:** Production recommendations established

---

## Executive Summary

After comprehensive benchmarking on a real codebase (julan_peppol, 285 files, PHP+Python), we established clear guidelines for when and how to use reranking with ogrep.

### The Rule

**Reranking helps weak embeddings but hurts strong embeddings.**

| Embedding | Without Rerank | With flashrank | Action |
|-----------|----------------|----------------|--------|
| OpenAI text-embedding-3-small | **0.700 MRR** | 0.550 (-21%) | ❌ Don't rerank |
| Nomic embed-text-v1.5 (local) | 0.545 MRR | **0.633** (+16%) | ✅ Use reranking |

---

## Benchmark Results

### Test Methodology

- **Ground truth:** 10 queries with known correct file paths
- **Metrics:** Hit@1, Hit@3, Hit@5, MRR (Mean Reciprocal Rank)
- **Codebase:** 285 files, ~1400 chunks (OpenAI) / ~4000 chunks (Nomic)
- **Hardware:** Linux x86_64, CPU-only (no GPU)

### OpenAI Embedding Results

| Reranker | Hit@1 | Hit@3 | Hit@5 | MRR |
|----------|-------|-------|-------|-----|
| **None (baseline)** | **6/10** | **8/10** | **8/10** | **0.700** |
| bge-m3 | 6/10 | 6/10 | 8/10 | 0.650 |
| minilm | 5/10 | 6/10 | 8/10 | 0.617 |
| flashrank | 5/10 | 6/10 | 6/10 | 0.550 |
| flashrank:mini | 4/10 | 5/10 | 7/10 | 0.478 |

**Conclusion:** Reranking HURTS OpenAI embeddings. Don't use it.

### Nomic Embedding Results (Local)

| Reranker | Hit@1 | Hit@3 | Hit@5 | MRR |
|----------|-------|-------|-------|-----|
| **flashrank** | **6/10** | **7/10** | 7/10 | **0.633** |
| minilm | 4/10 | 7/10 | 8/10 | 0.568 |
| None (baseline) | 4/10 | 6/10 | 8/10 | 0.545 |
| bge-m3 | 3/10 | 7/10 | 7/10 | 0.516 |
| flashrank:mini | 4/10 | 6/10 | 6/10 | 0.512 |

**Conclusion:** Reranking HELPS Nomic embeddings. Use flashrank.

---

## Reranker Comparison

### Current Options (Built-in)

| Model | Backend | Size | Speed (CPU) | Parallel-Safe | Verdict |
|-------|---------|------|-------------|---------------|---------|
| **flashrank** | ONNX | 4MB | ~200ms | ✅ Yes | **Default - best balance** |
| flashrank:mini | ONNX | 50MB | ~300ms | ✅ Yes | No benefit over flashrank |
| minilm | sentence-transformers | 90MB | ~2s | ❌ Needs lock | Optional |
| bge-m3 | sentence-transformers | 300MB | ~30s | ❌ Needs lock | ❌ Too slow on CPU |

### Why Current Rerankers Underperform on Code

1. **MS-MARCO trained:** All current rerankers (bge-m3, minilm, flashrank) are trained on MS-MARCO web search passages, not code.
2. **No code understanding:** They treat code as text, missing syntax, semantics, and structure.
3. **Strong embeddings don't need help:** OpenAI's embeddings are already well-calibrated for code search.

---

## Code-Specific Reranking Services (Future Investigation)

### API Services (Production-Ready)

#### 1. Voyage AI - Best for Code
- **Website:** https://www.voyageai.com/
- **Models:** `voyage-code-3` (embeddings), `rerank-2.5` (reranking)
- **Free tier:** 200M tokens free
- **Code-aware:** Understands code structure, not just text similarity
- **Used by:** Continue.dev AI coding assistant
- **Docs:** https://docs.voyageai.com/docs/reranker

#### 2. Jina AI - Code Search Support
- **Website:** https://jina.ai/reranker/
- **Models:** `jina-reranker-v3` (0.6B params, Oct 2025), `jina-code-embeddings-1.5b`
- **Features:** Explicit code search mode, 131K context, 100+ languages
- **Free tier:** 100 RPM, 100K TPM
- **Announcement:** https://jina.ai/news/jina-reranker-v2-for-agentic-rag-ultra-fast-multilingual-function-calling-and-code-search/

#### 3. Cohere Rerank
- **Website:** https://cohere.com/rerank
- **Code support:** Handles JSON, code, structured docs
- **Easy integration:** Few lines of code
- **Enterprise-focused**

### Self-Hosted Options (HuggingFace)

#### Code-Specific Models

| Model | Size | Use Case | Link |
|-------|------|----------|------|
| microsoft/unixcoder-base | 125M | Code search, multi-language | https://huggingface.co/microsoft/unixcoder-base |
| microsoft/codebert-base | 125M | NL-to-code retrieval | https://huggingface.co/microsoft/codebert-base |
| jinaai/jina-reranker-v3 | 0.6B | SOTA reranking with code | https://huggingface.co/jinaai/jina-reranker-v3 |

#### Recent Research (2025)

**LoRACode** (https://arxiv.org/html/2503.05315)
- Fine-tuned LoRA adapters for CodeBERT/UniXcoder
- Results: **+9.1% MRR** on Code2Code, **+86.69%** on Text2Code
- Trains in 25 min on 2x H100 GPUs
- Available on HuggingFace

---

## Production Recommendations

### For Maximum Quality (Cloud)

```bash
export OPENAI_API_KEY=...
ogrep index .
ogrep query "your search"  # NO --rerank flag
```

- **MRR: 0.700** (best achievable with current setup)
- Fast indexing: ~30s for 285 files
- Cost: ~$0.02 per index

### For Privacy/Offline (Local)

```bash
export OGREP_BASE_URL=http://localhost:1234/v1
export OGREP_MODEL=nomic
ogrep index .
ogrep query "your search" --rerank  # flashrank is default
```

- **MRR: 0.633** (-9.5% vs OpenAI)
- Zero cost, fully offline
- Slower indexing: ~17 min for 285 files

### Decision Matrix

| Requirement | Configuration |
|-------------|---------------|
| Maximum accuracy | OpenAI, no reranking |
| Privacy/compliance | Nomic + flashrank |
| Offline capability | Nomic + flashrank |
| Minimum cost | Nomic + flashrank |
| Fastest indexing | OpenAI |
| Fastest queries | Any, no reranking |

---

## Why This Matters

### The Problem We Solved

Query 3 ("export to CSV JSON") demonstrates the exact issue:
- Top result `TableExport.vue` is **exactly correct**
- Score is 0.0297 - appears "very weak"
- AI agents might distrust this result and enter retry loops

### The Solution

Hybrid confidence scoring that considers:
1. **Relative position:** Is this the best match available?
2. **Absolute quality:** How strong is the semantic match?
3. **Signal explanation:** Human-readable reason for the confidence level

Low absolute scores can still be "medium" confidence if they're the clear best match.

---

## Future Work

1. [ ] Integrate Voyage AI rerank-2.5 as optional backend
2. [ ] Test Jina reranker-v3 with code search mode
3. [ ] Evaluate UniXcoder/CodeBERT for self-hosted code reranking
4. [ ] GPU benchmarks for bge-m3 (may become viable)
5. [ ] Larger ground truth set (100+ queries)
6. [ ] Cross-repository validation

---

## References

### Benchmark Reports
- `test-reports/BENCHMARK-REPORT-2026-01-16.md` - Full benchmark data
- `test-reports/ground-truth-queries-julan-peppol.md` - Ground truth definitions
- `test-reports/embedding-quality-comparison.md` - OpenAI vs Nomic comparison

### External Resources
- Voyage AI Blog: https://blog.voyageai.com/
- Jina AI Reranker: https://jina.ai/reranker/
- Continue.dev on Voyage: https://blog.continue.dev/transforming-code-search-with-voyage-ai/
- LoRACode Paper: https://arxiv.org/html/2503.05315

---

*Document created: 2026-01-16*
*Last updated: 2026-01-16*
