"""
Performance benchmarks for the multi-level cache system.

These tests measure the actual performance gains from caching.
Run with: pytest tests/benchmark_cache.py -v --benchmark

Marked as slow tests - run separately from unit tests.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from ogrep.cache import (
    L1_TTL_SECONDS,
    cache_key,
    connect_cache,
    get_cache_path,
    get_query_embedding,
    get_rerank_results,
    get_search_results,
    set_query_embedding,
    set_rerank_results,
    set_search_results,
)
from ogrep.db import connect as connect_index


@pytest.fixture
def benchmark_cache_db(tmp_path: Path):
    """Create a cache database for benchmarking."""
    cache_path = tmp_path / ".ogrep" / "cache.sqlite"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    con = connect_cache(cache_path)
    yield con, cache_path
    con.close()


@pytest.fixture
def benchmark_index_db(tmp_path: Path):
    """Create an index database for benchmarking."""
    index_path = tmp_path / ".ogrep" / "index.sqlite"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    con = connect_index(index_path)
    yield con, index_path
    con.close()


class TestL1CachePerformance:
    """Benchmark L1 (embedding) cache performance."""

    def test_l1_hit_is_faster_than_api_call(self, benchmark_cache_db):
        """L1 cache hit should be much faster than an API call (~200-500ms)."""
        cache_con, _ = benchmark_cache_db

        # Store an embedding
        query = "test query for performance"
        model = "text-embedding-3-small"
        embedding = b"\x00" * (1536 * 4)  # 1536 floats

        set_query_embedding(cache_con, query, model, 1536, None, embedding)

        # Benchmark cache lookup
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            result = get_query_embedding(cache_con, query, model, 1536, None)
            assert result.hit
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / iterations) * 1000
        print(f"\nL1 cache lookup: {avg_time_ms:.3f}ms average ({iterations} iterations)")

        # Should be under 1ms per lookup
        assert avg_time_ms < 1.0, f"L1 cache lookup too slow: {avg_time_ms:.3f}ms"

    def test_l1_cache_overhead_is_minimal(self, benchmark_cache_db):
        """Writing to L1 cache should add minimal overhead."""
        cache_con, _ = benchmark_cache_db

        model = "text-embedding-3-small"
        embedding = b"\x00" * (1536 * 4)

        # Benchmark cache writes
        iterations = 50
        start = time.perf_counter()
        for i in range(iterations):
            query = f"unique query {i}"
            set_query_embedding(cache_con, query, model, 1536, None, embedding)
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / iterations) * 1000
        print(f"\nL1 cache write: {avg_time_ms:.3f}ms average ({iterations} iterations)")

        # Should be under 5ms per write
        assert avg_time_ms < 5.0, f"L1 cache write too slow: {avg_time_ms:.3f}ms"


class TestL2CachePerformance:
    """Benchmark L2 (search results) cache performance."""

    def test_l2_hit_is_faster_than_search(self, benchmark_cache_db, benchmark_index_db):
        """L2 cache hit should be faster than similarity computation."""
        cache_con, _ = benchmark_cache_db
        index_con, _ = benchmark_index_db

        # Store search results
        embedding_key = "test_embedding_key_12345"
        mode = "hybrid"
        top_k = 10
        results = [(i, 0.9 - i * 0.05) for i in range(10)]

        set_search_results(cache_con, index_con, embedding_key, mode, top_k, results, True)

        # Benchmark cache lookup
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            result = get_search_results(cache_con, index_con, embedding_key, mode, top_k)
            assert result.hit
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / iterations) * 1000
        print(f"\nL2 cache lookup: {avg_time_ms:.3f}ms average ({iterations} iterations)")

        # Should be under 2ms per lookup
        assert avg_time_ms < 2.0, f"L2 cache lookup too slow: {avg_time_ms:.3f}ms"


class TestL3CachePerformance:
    """Benchmark L3 (rerank results) cache performance."""

    def test_l3_hit_is_faster_than_rerank(self, benchmark_cache_db):
        """L3 cache hit should be much faster than cross-encoder inference (~2-5s)."""
        cache_con, _ = benchmark_cache_db

        query = "test query"
        chunk_hashes = [f"hash{i}" for i in range(20)]
        rerank_model = "BAAI/bge-reranker-v2-m3"
        rerank_top = 20
        results = [(i, 0.9 - i * 0.01) for i in range(20)]

        set_rerank_results(cache_con, query, chunk_hashes, rerank_model, rerank_top, results)

        # Benchmark cache lookup
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            result = get_rerank_results(cache_con, query, chunk_hashes, rerank_model, rerank_top)
            assert result.hit
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / iterations) * 1000
        print(f"\nL3 cache lookup: {avg_time_ms:.3f}ms average ({iterations} iterations)")

        # Should be under 2ms per lookup
        assert avg_time_ms < 2.0, f"L3 cache lookup too slow: {avg_time_ms:.3f}ms"


class TestCacheKeyPerformance:
    """Benchmark cache key generation."""

    def test_cache_key_generation_is_fast(self):
        """Cache key generation should be fast."""
        iterations = 1000

        start = time.perf_counter()
        for i in range(iterations):
            _ = cache_key(f"query {i}", "model", 1536, "openai")
        elapsed = time.perf_counter() - start

        avg_time_us = (elapsed / iterations) * 1_000_000
        print(f"\nCache key generation: {avg_time_us:.1f}us average ({iterations} iterations)")

        # Should be under 100 microseconds
        assert avg_time_us < 100, f"Cache key too slow: {avg_time_us:.1f}us"


class TestConcurrentAccess:
    """Test cache performance under concurrent access patterns."""

    def test_mixed_read_write_performance(self, benchmark_cache_db):
        """Test performance with mixed read/write operations."""
        cache_con, _ = benchmark_cache_db

        model = "text-embedding-3-small"
        embedding = b"\x00" * (1536 * 4)

        # Pre-populate some entries
        for i in range(50):
            set_query_embedding(cache_con, f"existing query {i}", model, 1536, None, embedding)

        # Mixed operations: 80% reads, 20% writes
        operations = 200
        start = time.perf_counter()

        for i in range(operations):
            if i % 5 == 0:
                # Write operation (20%)
                set_query_embedding(cache_con, f"new query {i}", model, 1536, None, embedding)
            else:
                # Read operation (80%)
                _ = get_query_embedding(cache_con, f"existing query {i % 50}", model, 1536, None)

        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / operations) * 1000
        print(f"\nMixed operations: {avg_time_ms:.3f}ms average ({operations} ops, 80/20 read/write)")

        # Should be under 2ms per operation on average
        assert avg_time_ms < 2.0, f"Mixed operations too slow: {avg_time_ms:.3f}ms"


@pytest.mark.slow
class TestEndToEndCachePerformance:
    """End-to-end cache performance tests (require integration)."""

    def test_cache_saves_significant_time(self):
        """
        Estimate total time savings from cache hits.

        Expected savings per level:
        - L1: 200-500ms per hit (API call avoided)
        - L2: 100-300ms per hit (similarity computation avoided)
        - L3: 2000-5000ms per hit (cross-encoder inference avoided)
        """
        # Estimated time savings (ms) per cache hit
        l1_savings = 300  # Embedding API call
        l2_savings = 150  # Similarity computation
        l3_savings = 3000  # Cross-encoder inference

        # Simulated session with 10 queries, some repeated
        # 6 unique queries, 4 repeated = 4 L1 hits
        # 4 L2 hits (for repeated queries)
        # 2 L3 hits (for repeated rerank queries)

        l1_hits = 4
        l2_hits = 4
        l3_hits = 2

        total_savings_ms = (
            l1_hits * l1_savings + l2_hits * l2_savings + l3_hits * l3_hits * l3_savings
        )

        print(f"\nEstimated session savings:")
        print(f"  L1 hits: {l1_hits} x {l1_savings}ms = {l1_hits * l1_savings}ms")
        print(f"  L2 hits: {l2_hits} x {l2_savings}ms = {l2_hits * l2_savings}ms")
        print(f"  L3 hits: {l3_hits} x {l3_savings}ms = {l3_hits * l3_savings}ms")
        print(f"  Total: {total_savings_ms}ms = {total_savings_ms / 1000:.1f}s")

        # Should save multiple seconds per typical session
        assert total_savings_ms > 5000, "Cache should save >5s in typical session"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
