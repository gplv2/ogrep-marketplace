"""
TDD tests for multi-level cache system.

Tests are written FIRST, then implementation follows.
Run with: pytest tests/test_cache.py -v

Cache Levels:
- L1: Query embeddings (TTL-based, 24h default)
- L2: Search results (db_version invalidated)
- L3: Rerank results (content-addressable)
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

# === Fixtures ===


@pytest.fixture
def temp_dir(tmp_path):
    """Create temporary directory for test databases."""
    ogrep_dir = tmp_path / ".ogrep"
    ogrep_dir.mkdir()
    return ogrep_dir


@pytest.fixture
def cache_db(temp_dir):
    """Create cache database connection."""
    from ogrep.cache import connect_cache

    cache_path = temp_dir / "cache.sqlite"
    return connect_cache(cache_path)


@pytest.fixture
def index_db(temp_dir):
    """Create index database connection with db_version."""
    from ogrep.db import connect

    index_path = temp_dir / "index.sqlite"
    con = connect(index_path)
    # Initialize db_version
    con.execute("INSERT OR REPLACE INTO index_metadata (key, value) VALUES ('db_version', '1')")
    con.commit()
    return con


@pytest.fixture
def sample_embedding():
    """Create sample embedding bytes (1536 dimensions, float32)."""
    import array

    # Create normalized embedding
    values = [0.1] * 1536
    arr = array.array("f", values)
    return arr.tobytes()


@pytest.fixture
def sample_results():
    """Sample search results for caching."""
    return [
        (1, 0.95),  # (chunk_id, score)
        (5, 0.87),
        (12, 0.72),
        (8, 0.65),
        (3, 0.58),
    ]


@pytest.fixture
def sample_chunk_hashes():
    """Sample chunk text hashes for L3 cache."""
    return [
        "a1b2c3d4e5f6",
        "b2c3d4e5f6a1",
        "c3d4e5f6a1b2",
    ]


# === L1: Query Embedding Cache Tests ===


class TestL1QueryEmbeddingCache:
    """Tests for query embedding cache (TTL-based)."""

    def test_cache_miss_returns_none(self, cache_db):
        """Empty cache returns CacheResult with hit=False."""
        from ogrep.cache import get_query_embedding

        result = get_query_embedding(cache_db, "test query", "text-embedding-3-small", 1536, None)
        assert result.hit is False
        assert result.data is None

    def test_cache_hit_returns_embedding(self, cache_db, sample_embedding):
        """Stored embedding is retrievable."""
        from ogrep.cache import get_query_embedding, set_query_embedding

        # Store embedding
        set_query_embedding(
            cache_db, "test query", "text-embedding-3-small", 1536, None, sample_embedding
        )

        # Retrieve it
        result = get_query_embedding(cache_db, "test query", "text-embedding-3-small", 1536, None)
        assert result.hit is True
        assert result.data == sample_embedding

    def test_different_query_different_key(self, cache_db, sample_embedding):
        """Different queries have different cache keys."""
        from ogrep.cache import get_query_embedding, set_query_embedding

        # Store for query A
        set_query_embedding(
            cache_db, "query A", "text-embedding-3-small", 1536, None, sample_embedding
        )

        # Query B should miss
        result = get_query_embedding(cache_db, "query B", "text-embedding-3-small", 1536, None)
        assert result.hit is False

    def test_different_model_different_key(self, cache_db, sample_embedding):
        """Same query, different model = different cache key."""
        from ogrep.cache import get_query_embedding, set_query_embedding

        # Store with model A
        set_query_embedding(
            cache_db, "test query", "text-embedding-3-small", 1536, None, sample_embedding
        )

        # Different model should miss
        result = get_query_embedding(cache_db, "test query", "text-embedding-3-large", 3072, None)
        assert result.hit is False

    def test_different_base_url_different_key(self, cache_db, sample_embedding):
        """Local vs cloud = different cache key."""
        from ogrep.cache import get_query_embedding, set_query_embedding

        # Store with cloud (None base_url)
        set_query_embedding(
            cache_db, "test query", "nomic-embed-text-v1.5", 768, None, sample_embedding
        )

        # Local server should miss
        result = get_query_embedding(
            cache_db, "test query", "nomic-embed-text-v1.5", 768, "http://localhost:1234"
        )
        assert result.hit is False

    def test_ttl_expiry(self, cache_db, sample_embedding):
        """Entry expires after TTL."""
        from ogrep.cache import L1_TTL_SECONDS, get_query_embedding, set_query_embedding

        # Store embedding
        set_query_embedding(
            cache_db, "test query", "text-embedding-3-small", 1536, None, sample_embedding
        )

        # Should hit immediately
        result = get_query_embedding(cache_db, "test query", "text-embedding-3-small", 1536, None)
        assert result.hit is True

        # Mock time to be after TTL
        with patch("time.time", return_value=time.time() + L1_TTL_SECONDS + 1):
            result = get_query_embedding(
                cache_db, "test query", "text-embedding-3-small", 1536, None
            )
            assert result.hit is False

    def test_hit_count_increments(self, cache_db, sample_embedding):
        """hit_count increases on each access."""
        from ogrep.cache import get_query_embedding, set_query_embedding

        # Store embedding
        set_query_embedding(
            cache_db, "test query", "text-embedding-3-small", 1536, None, sample_embedding
        )

        # Access multiple times
        for _ in range(3):
            get_query_embedding(cache_db, "test query", "text-embedding-3-small", 1536, None)

        # Check hit_count in database
        row = cache_db.execute("SELECT hit_count FROM query_embeddings LIMIT 1").fetchone()
        assert row[0] == 3

    def test_lru_eviction(self, cache_db, sample_embedding):
        """Oldest entries evicted when over limit."""
        from ogrep.cache import evict_lru, set_query_embedding

        # Insert more than max entries
        for i in range(10):
            set_query_embedding(
                cache_db, f"query {i}", "text-embedding-3-small", 1536, None, sample_embedding
            )
            time.sleep(0.01)  # Ensure different timestamps

        # Evict down to 5
        evicted = evict_lru(cache_db, "query_embeddings", max_entries=5)
        assert evicted == 5

        # Verify only 5 remain
        count = cache_db.execute("SELECT COUNT(*) FROM query_embeddings").fetchone()[0]
        assert count == 5


# === L2: Search Results Cache Tests ===


class TestL2SearchResultsCache:
    """Tests for search results cache (db_version invalidated)."""

    def test_cache_miss_returns_none(self, cache_db, index_db):
        """Empty cache returns CacheResult with hit=False."""
        from ogrep.cache import get_search_results

        result = get_search_results(cache_db, index_db, "embedding_key_abc", "hybrid", 10)
        assert result.hit is False
        assert result.data is None

    def test_cache_hit_returns_results(self, cache_db, index_db, sample_results):
        """Stored results are retrievable."""
        from ogrep.cache import get_search_results, set_search_results

        # Store results
        set_search_results(
            cache_db, index_db, "embedding_key_abc", "hybrid", 10, sample_results, True
        )

        # Retrieve them
        result = get_search_results(cache_db, index_db, "embedding_key_abc", "hybrid", 10)
        assert result.hit is True
        assert result.data == sample_results
        assert result.fts_available is True

    def test_db_version_mismatch_returns_none(self, cache_db, index_db, sample_results):
        """Stale db_version = cache miss."""
        from ogrep.cache import get_search_results, increment_db_version, set_search_results

        # Store results at version 1
        set_search_results(
            cache_db, index_db, "embedding_key_abc", "hybrid", 10, sample_results, True
        )

        # Increment db_version
        increment_db_version(index_db)

        # Should miss now
        result = get_search_results(cache_db, index_db, "embedding_key_abc", "hybrid", 10)
        assert result.hit is False

    def test_different_mode_different_key(self, cache_db, index_db, sample_results):
        """Same query, different mode = different cache key."""
        from ogrep.cache import get_search_results, set_search_results

        # Store with hybrid mode
        set_search_results(
            cache_db, index_db, "embedding_key_abc", "hybrid", 10, sample_results, True
        )

        # Semantic mode should miss
        result = get_search_results(cache_db, index_db, "embedding_key_abc", "semantic", 10)
        assert result.hit is False

    def test_different_top_k_different_key(self, cache_db, index_db, sample_results):
        """Same query, different top_k = different cache key."""
        from ogrep.cache import get_search_results, set_search_results

        # Store with top_k=10
        set_search_results(
            cache_db, index_db, "embedding_key_abc", "hybrid", 10, sample_results, True
        )

        # top_k=5 should miss
        result = get_search_results(cache_db, index_db, "embedding_key_abc", "hybrid", 5)
        assert result.hit is False


# === L3: Rerank Results Cache Tests ===


class TestL3RerankResultsCache:
    """Tests for rerank results cache (content-addressable)."""

    def test_cache_miss_returns_none(self, cache_db, sample_chunk_hashes):
        """Empty cache returns CacheResult with hit=False."""
        from ogrep.cache import get_rerank_results

        result = get_rerank_results(
            cache_db, "test query", sample_chunk_hashes, "BAAI/bge-reranker-v2-m3", 50
        )
        assert result.hit is False
        assert result.data is None

    def test_cache_hit_returns_scores(self, cache_db, sample_chunk_hashes, sample_results):
        """Stored scores are retrievable."""
        from ogrep.cache import get_rerank_results, set_rerank_results

        # Store rerank results
        set_rerank_results(
            cache_db,
            "test query",
            sample_chunk_hashes,
            "BAAI/bge-reranker-v2-m3",
            50,
            sample_results,
        )

        # Retrieve them
        result = get_rerank_results(
            cache_db, "test query", sample_chunk_hashes, "BAAI/bge-reranker-v2-m3", 50
        )
        assert result.hit is True
        assert result.data == sample_results

    def test_different_chunk_content_different_key(self, cache_db, sample_results):
        """Different chunk hashes = different cache key."""
        from ogrep.cache import get_rerank_results, set_rerank_results

        hashes_a = ["hash1", "hash2", "hash3"]
        hashes_b = ["hash4", "hash5", "hash6"]

        # Store with hashes_a
        set_rerank_results(
            cache_db, "test query", hashes_a, "BAAI/bge-reranker-v2-m3", 50, sample_results
        )

        # hashes_b should miss
        result = get_rerank_results(cache_db, "test query", hashes_b, "BAAI/bge-reranker-v2-m3", 50)
        assert result.hit is False

    def test_same_content_different_order_hits_cache(self, cache_db, sample_results):
        """Content-addressable: same hashes in different order = cache hit."""
        from ogrep.cache import get_rerank_results, set_rerank_results

        hashes_ordered = ["a", "b", "c"]
        hashes_shuffled = ["c", "a", "b"]

        # Store with one order
        set_rerank_results(
            cache_db, "test query", hashes_ordered, "BAAI/bge-reranker-v2-m3", 50, sample_results
        )

        # Different order should still hit (sorted internally)
        result = get_rerank_results(
            cache_db, "test query", hashes_shuffled, "BAAI/bge-reranker-v2-m3", 50
        )
        assert result.hit is True

    def test_different_rerank_model_different_key(
        self, cache_db, sample_chunk_hashes, sample_results
    ):
        """Same chunks, different model = different cache key."""
        from ogrep.cache import get_rerank_results, set_rerank_results

        # Store with model A
        set_rerank_results(
            cache_db,
            "test query",
            sample_chunk_hashes,
            "BAAI/bge-reranker-v2-m3",
            50,
            sample_results,
        )

        # Different model should miss
        result = get_rerank_results(
            cache_db, "test query", sample_chunk_hashes, "cross-encoder/ms-marco-MiniLM-L-6-v2", 50
        )
        assert result.hit is False


# === db_version Tests ===


class TestDbVersion:
    """Tests for db_version tracking in index.sqlite."""

    def test_get_db_version_default(self, temp_dir):
        """New index has db_version=0."""
        from ogrep.cache import get_db_version
        from ogrep.db import connect

        index_path = temp_dir / "fresh_index.sqlite"
        con = connect(index_path)
        version = get_db_version(con)
        assert version == 0

    def test_increment_db_version(self, index_db):
        """Incrementing version works correctly."""
        from ogrep.cache import get_db_version, increment_db_version

        # Initial version is 1 (set in fixture)
        assert get_db_version(index_db) == 1

        # Increment
        new_version = increment_db_version(index_db)
        assert new_version == 2
        assert get_db_version(index_db) == 2

        # Increment again
        new_version = increment_db_version(index_db)
        assert new_version == 3


# === Stats Tracking Tests ===


class TestCacheStats:
    """Tests for cache statistics tracking."""

    def test_log_cache_event(self, cache_db):
        """Cache events are logged to stats table."""
        from ogrep.cache import log_cache_event

        log_cache_event(cache_db, "L1", "hit", time_saved_ms=350)
        log_cache_event(cache_db, "L2", "miss")
        log_cache_event(cache_db, "L3", "hit", time_saved_ms=3200)

        count = cache_db.execute("SELECT COUNT(*) FROM cache_stats").fetchone()[0]
        assert count == 3

    def test_get_cache_report(self, cache_db):
        """Cache report aggregates stats correctly."""
        from ogrep.cache import get_cache_report, log_cache_event

        # Log some events
        for _ in range(5):
            log_cache_event(cache_db, "L1", "hit", time_saved_ms=300)
        for _ in range(2):
            log_cache_event(cache_db, "L1", "miss")
        for _ in range(3):
            log_cache_event(cache_db, "L2", "hit", time_saved_ms=150)
        for _ in range(3):
            log_cache_event(cache_db, "L2", "miss")

        report = get_cache_report(cache_db, since_hours=1)

        assert report["L1"]["hits"] == 5
        assert report["L1"]["misses"] == 2
        assert report["L1"]["hit_rate"] == pytest.approx(5 / 7 * 100, rel=0.01)
        assert report["L1"]["time_saved_ms"] == 1500

        assert report["L2"]["hits"] == 3
        assert report["L2"]["misses"] == 3
        assert report["L2"]["hit_rate"] == 50.0


# === Maintenance Tests ===


class TestCacheMaintenance:
    """Tests for cache maintenance operations."""

    def test_clear_expired_l1(self, cache_db, sample_embedding):
        """Expired L1 entries are removed."""
        from ogrep.cache import clear_expired_l1

        # Insert entries with old timestamps
        cache_db.execute(
            """INSERT INTO query_embeddings
               (cache_key, query_text, model, dimensions, embedding, created_at, hit_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("old_key", "old query", "model", 1536, sample_embedding, 0.0, 0),
        )
        cache_db.commit()

        # Clear expired
        removed = clear_expired_l1(cache_db)
        assert removed == 1

    def test_clear_stale_l2(self, cache_db, sample_results):
        """L2 entries with old db_version are removed."""
        from ogrep.cache import clear_stale_l2

        # Insert entries with old db_version
        cache_db.execute(
            """INSERT INTO search_results
               (cache_key, embedding_key, mode, top_k, db_version, results, fts_available, created_at, hit_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("key1", "emb1", "hybrid", 10, 1, json.dumps(sample_results), 1, time.time(), 0),
        )
        cache_db.execute(
            """INSERT INTO search_results
               (cache_key, embedding_key, mode, top_k, db_version, results, fts_available, created_at, hit_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("key2", "emb2", "hybrid", 10, 5, json.dumps(sample_results), 1, time.time(), 0),
        )
        cache_db.commit()

        # Clear entries older than version 5
        removed = clear_stale_l2(cache_db, current_db_version=5)
        assert removed == 1

        # Only version 5 entry should remain
        count = cache_db.execute("SELECT COUNT(*) FROM search_results").fetchone()[0]
        assert count == 1

    def test_clear_all_caches(
        self, cache_db, sample_embedding, sample_results, sample_chunk_hashes
    ):
        """All cache tables are cleared."""
        from ogrep.cache import clear_all_caches, set_query_embedding

        # Add some data
        set_query_embedding(cache_db, "q1", "model", 1536, None, sample_embedding)

        cache_db.execute(
            """INSERT INTO search_results
               (cache_key, embedding_key, mode, top_k, db_version, results, fts_available, created_at, hit_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("key1", "emb1", "hybrid", 10, 1, json.dumps(sample_results), 1, time.time(), 0),
        )

        cache_db.execute(
            """INSERT INTO rerank_results
               (cache_key, query_text, chunk_content_hash, rerank_model, rerank_top, results, created_at, hit_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("key1", "query", "hash", "model", 50, json.dumps(sample_results), time.time(), 0),
        )
        cache_db.commit()

        # Clear all
        result = clear_all_caches(cache_db)

        assert result["query_embeddings"] >= 1
        assert result["search_results"] >= 1
        assert result["rerank_results"] >= 1

        # Verify all empty
        for table in ["query_embeddings", "search_results", "rerank_results"]:
            count = cache_db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == 0


# === Integration Tests ===


class TestCacheIntegration:
    """End-to-end cache behavior tests."""

    @pytest.fixture
    def indexed_repo(self, temp_dir, monkeypatch):
        """Create an indexed repository for integration tests."""
        # This fixture would set up a real indexed repo
        # For now, mark as not implemented
        pytest.skip("Integration test requires full indexing infrastructure")

    def test_no_cache_flag_bypasses_all(self, indexed_repo):
        """--no-cache flag works."""
        pytest.skip("Integration test requires full CLI infrastructure")

    def test_cache_disabled_env_bypasses_all(self, indexed_repo, monkeypatch):
        """OGREP_CACHE_DISABLED works."""
        pytest.skip("Integration test requires full CLI infrastructure")


# === Performance Benchmark Tests ===


class TestCachePerformance:
    """Benchmark tests (marked slow, run separately)."""

    @pytest.mark.slow
    def test_l1_lookup_performance(self, cache_db, sample_embedding):
        """L1 cache lookup should be fast (<10ms)."""
        from ogrep.cache import get_query_embedding, set_query_embedding

        # Store embedding
        set_query_embedding(
            cache_db, "test query", "text-embedding-3-small", 1536, None, sample_embedding
        )

        # Measure lookup time
        start = time.perf_counter()
        for _ in range(100):
            get_query_embedding(cache_db, "test query", "text-embedding-3-small", 1536, None)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 10, f"L1 lookup too slow: {avg_ms:.2f}ms average"

    @pytest.mark.slow
    def test_l2_lookup_performance(self, cache_db, index_db, sample_results):
        """L2 cache lookup should be fast (<10ms)."""
        from ogrep.cache import get_search_results, set_search_results

        # Store results
        set_search_results(
            cache_db, index_db, "embedding_key_abc", "hybrid", 10, sample_results, True
        )

        # Measure lookup time
        start = time.perf_counter()
        for _ in range(100):
            get_search_results(cache_db, index_db, "embedding_key_abc", "hybrid", 10)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 10, f"L2 lookup too slow: {avg_ms:.2f}ms average"

    @pytest.mark.slow
    def test_l3_lookup_performance(self, cache_db, sample_chunk_hashes, sample_results):
        """L3 cache lookup should be fast (<10ms)."""
        from ogrep.cache import get_rerank_results, set_rerank_results

        # Store results
        set_rerank_results(
            cache_db,
            "test query",
            sample_chunk_hashes,
            "BAAI/bge-reranker-v2-m3",
            50,
            sample_results,
        )

        # Measure lookup time
        start = time.perf_counter()
        for _ in range(100):
            get_rerank_results(
                cache_db, "test query", sample_chunk_hashes, "BAAI/bge-reranker-v2-m3", 50
            )
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 10, f"L3 lookup too slow: {avg_ms:.2f}ms average"


# === Cache Cleanup Tests ===


class TestCacheCleanup:
    """Tests for cache file cleanup when index is deleted."""

    def test_get_cache_path_from_index_path(self, temp_dir):
        """get_cache_path derives cache path from index path."""
        from ogrep.cache import get_cache_path

        index_path = temp_dir / "index.sqlite"
        cache_path = get_cache_path(index_path)

        assert cache_path == temp_dir / "cache.sqlite"
        assert cache_path.parent == index_path.parent

    def test_reset_removes_cache_file(self, tmp_path, monkeypatch):
        """Reset command should delete cache.sqlite along with index.sqlite."""
        import argparse

        from ogrep.cache import connect_cache, get_cache_path, set_query_embedding
        from ogrep.commands.reset import cmd_reset
        from ogrep.db import connect

        # Create .ogrep directory with index and cache
        ogrep_dir = tmp_path / ".ogrep"
        ogrep_dir.mkdir()
        index_path = ogrep_dir / "index.sqlite"
        cache_path = get_cache_path(index_path)

        # Create index database
        index_con = connect(index_path)
        index_con.close()

        # Create cache database with some data
        cache_con = connect_cache(cache_path)
        set_query_embedding(cache_con, "test query", "model", 1536, None, b"embedding")
        cache_con.close()

        # Verify both files exist
        assert index_path.exists()
        assert cache_path.exists()

        # Run reset command with --all to delete entire database
        # (default behavior is now branch-scoped reset)
        args = argparse.Namespace(
            force=True,
            json=True,
            db=None,
            profile=None,
            global_cache=False,
            repo_root=tmp_path,
            all=True,  # Required to delete entire database (new branch-aware behavior)
        )

        result = cmd_reset(args)

        # Verify both files are deleted
        assert result == 0
        assert not index_path.exists()
        assert not cache_path.exists()

    def test_reindex_removes_cache_file(self, tmp_path, monkeypatch):
        """Reindex command should delete cache.sqlite along with index.sqlite."""
        import argparse

        from ogrep.cache import connect_cache, get_cache_path, set_query_embedding
        from ogrep.db import connect

        # Set up test environment
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        # Create .ogrep directory with index and cache
        ogrep_dir = tmp_path / ".ogrep"
        ogrep_dir.mkdir()
        index_path = ogrep_dir / "index.sqlite"
        cache_path = get_cache_path(index_path)

        # Create a test file to index
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass")

        # Create index database
        index_con = connect(index_path)
        index_con.close()

        # Create cache database with some data
        cache_con = connect_cache(cache_path)
        set_query_embedding(cache_con, "test query", "model", 1536, None, b"embedding")
        cache_con.close()

        # Verify both files exist
        assert index_path.exists()
        assert cache_path.exists()

        # Import reindex command
        from ogrep.commands.reindex import cmd_reindex

        # Mock the index_path function to avoid real API calls
        def mock_index_path(**kwargs):
            from ogrep.indexer import IndexStats

            # Create the new index database
            new_con = connect(kwargs["db_path"])
            new_con.close()
            return IndexStats(
                files_scanned=1,
                files_indexed=1,
                files_skipped=0,
                chunks_total=1,
                chunks_reused=0,
                chunks_reused_global=0,
                chunks_reused_local=0,
                chunks_embedded=1,
            )

        monkeypatch.setattr("ogrep.commands.reindex.index_path", mock_index_path)

        # Run reindex command
        args = argparse.Namespace(
            path=str(tmp_path),
            json=True,
            db=None,
            profile=None,
            global_cache=False,
            repo_root=tmp_path,
            model="text-embedding-3-small",
            dimensions=1536,
            chunk_lines=60,
            overlap=10,
            max_bytes=1024 * 1024,
            exclude=[],
            include=[],
            ast=False,
        )

        result = cmd_reindex(args)

        # Verify old cache is deleted (new index is created)
        assert result == 0
        assert index_path.exists()  # New index was created
        assert not cache_path.exists()  # Old cache was deleted
