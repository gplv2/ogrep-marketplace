# Cache Performance Benchmark Report

**Date:** 2026-01-15
**Branch:** feature/output-cache
**Hardware:** CPU-only (no GPU)

## Summary

The multi-level cache system provides significant performance improvements, especially for repeated queries with reranking.

## Benchmark Results

| Test | Cold (no cache) | Warm (cached) | Speedup |
|------|-----------------|---------------|---------|
| **Basic Query** | 458ms | 6ms | **76x faster** |
| **Query + Rerank** | 128,296ms (~2 min) | 2,821ms (~3s) | **45x faster** |

## Cache Levels Performance

| Level | Description | Time Saved per Hit | Use Case |
|-------|-------------|-------------------|----------|
| **L1** | Embedding cache | ~350ms | Avoids OpenAI API call |
| **L2** | Search results cache | ~180ms | Skips similarity computation |
| **L3** | Rerank results cache | **~3,200ms** | Skips cross-encoder inference |

## Detailed Results

### Test 1: Basic Query (L1 + L2 cache)

```
Query: "error handling" -n 5

Cold:  1159ms total (458ms search)
Warm:   671ms total (6ms search)

Search time improvement: 458ms → 6ms (76x faster)
```

### Test 2: Query with Reranking (L1 + L2 + L3 cache)

```
Query: "function definition" -n 5 --rerank

Cold:  129,867ms total (128,296ms search+rerank)
Warm:    4,148ms total (2,821ms search+rerank)

Search+rerank improvement: 128s → 2.8s (45x faster)
```

## Cache Statistics After Benchmark

```
── Cache Stats ──
  File: .ogrep/cache.sqlite
  Size: 60.0 KB

  Entries:
    Level           Count     Hits
    ──────────────────────────────
    Embeddings          2        2
    Search              2        2
    Rerank              1        1
    ──────────────────────────────
    Total               5

  Performance (lifetime):
    Level            Hits   Misses       Rate        Saved
    ────────────────────────────────────────────────────
    Embeddings          2        2      50.0%        700ms
    Search              2        2      50.0%        360ms
    Rerank              1        1      50.0%         3.2s
    ────────────────────────────────────────────────────
    Total               5        5      50.0%         4.3s
```

## Key Observations

1. **L3 (Rerank) provides the biggest win** - Cross-encoder inference on CPU is extremely slow (~2+ minutes for 50 candidates). With caching, repeated queries return in ~3 seconds.

2. **L1 (Embeddings) saves API costs** - Each cache hit avoids an OpenAI API call, saving both time (~350ms) and money.

3. **L2 (Search) improves responsiveness** - Even without reranking, cached search results return in under 10ms.

4. **Cache invalidation works correctly** - L2 cache invalidates when files change (db_version), L3 uses content-addressable keys.

## Use Cases

- **AI Tools**: Repeated queries during a conversation benefit from all cache levels
- **Interactive Development**: Same query patterns during debugging hit cache frequently
- **CI/CD**: Repeated searches in automated pipelines benefit from L1+L2 caching

## Recommendations

1. **Enable caching by default** (already implemented)
2. **Use `--rerank` for important queries** - the cache makes it practical even on CPU
3. **Run `ogrep cache-report`** periodically to monitor hit rates
4. **Clear cache with `ogrep cache-report --clear`** if results seem stale

## Test Environment

- Python 3.12.8
- SQLite 3.45.3
- No GPU (CPU-only cross-encoder inference)
- Index: 533 chunks, 54 files
- Embedding model: text-embedding-3-small (1536D)
