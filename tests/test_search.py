"""Tests for ogrep.search module."""

from __future__ import annotations

import array
from pathlib import Path

import pytest

from ogrep.db import connect
from ogrep.embed import embed_texts
from ogrep.search import (
    FilterStats,
    Hit,
    HybridConfidence,
    PathFilter,
    _dot_py,
    _rrf_score,
    assign_confidence,
    compute_hybrid_confidence,
    filter_hits_by_path,
    get_absolute_quality,
    get_confidence_level,
    get_relative_confidence,
    is_simple_pattern,
    matches_any_pattern,
    query,
)


class TestHitDataclass:
    """Tests for Hit dataclass."""

    def test_hit_creation(self) -> None:
        """Test creating a Hit instance."""
        hit = Hit(
            score=0.95,
            path="/path/to/file.py",
            start_line=10,
            end_line=20,
            text="def hello():\n    pass",
            chunk_id=42,
            chunk_index=2,
            confidence="high",
        )
        assert hit.score == 0.95
        assert hit.path == "/path/to/file.py"
        assert hit.start_line == 10
        assert hit.end_line == 20
        assert "hello" in hit.text
        assert hit.chunk_id == 42
        assert hit.chunk_index == 2
        assert hit.confidence == "high"

    def test_hit_is_frozen(self) -> None:
        """Test that Hit is immutable."""
        hit = Hit(
            score=0.5,
            path="/test.py",
            start_line=1,
            end_line=5,
            text="test",
            chunk_id=1,
            chunk_index=0,
            confidence="low",
        )
        with pytest.raises(AttributeError):  # Frozen dataclass
            hit.score = 0.9  # type: ignore[misc]

    def test_hit_comparison(self) -> None:
        """Test that hits with same values are equal."""
        hit1 = Hit(
            score=0.5,
            path="/test.py",
            start_line=1,
            end_line=5,
            text="test",
            chunk_id=1,
            chunk_index=0,
            confidence="low",
        )
        hit2 = Hit(
            score=0.5,
            path="/test.py",
            start_line=1,
            end_line=5,
            text="test",
            chunk_id=1,
            chunk_index=0,
            confidence="low",
        )
        assert hit1 == hit2

    def test_hit_different_scores(self) -> None:
        """Test that hits with different scores are not equal."""
        hit1 = Hit(
            score=0.5,
            path="/test.py",
            start_line=1,
            end_line=5,
            text="test",
            chunk_id=1,
            chunk_index=0,
            confidence="low",
        )
        hit2 = Hit(
            score=0.6,
            path="/test.py",
            start_line=1,
            end_line=5,
            text="test",
            chunk_id=1,
            chunk_index=0,
            confidence="low",
        )
        assert hit1 != hit2


class TestDotProduct:
    """Tests for _dot_py function (pure Python fallback)."""

    def test_dot_product_simple(self) -> None:
        """Test dot product of simple vectors."""
        a = array.array("f", [1.0, 2.0, 3.0])
        b = array.array("f", [4.0, 5.0, 6.0])
        # 1*4 + 2*5 + 3*6 = 4 + 10 + 18 = 32
        result = _dot_py(a, b)
        assert abs(result - 32.0) < 1e-5

    def test_dot_product_unit_vectors(self) -> None:
        """Test dot product of orthogonal unit vectors."""
        a = array.array("f", [1.0, 0.0, 0.0])
        b = array.array("f", [0.0, 1.0, 0.0])
        result = _dot_py(a, b)
        assert abs(result) < 1e-10  # Should be 0

    def test_dot_product_same_vector(self) -> None:
        """Test dot product of normalized vector with itself is 1."""
        # Normalize [3, 4] to [0.6, 0.8]
        a = array.array("f", [0.6, 0.8])
        result = _dot_py(a, a)
        assert abs(result - 1.0) < 1e-5

    def test_dot_product_negative_values(self) -> None:
        """Test dot product with negative values."""
        a = array.array("f", [1.0, -2.0])
        b = array.array("f", [-3.0, 4.0])
        # 1*(-3) + (-2)*4 = -3 + (-8) = -11
        result = _dot_py(a, b)
        assert abs(result - (-11.0)) < 1e-5

    def test_dot_product_zeros(self) -> None:
        """Test dot product with zero vector."""
        a = array.array("f", [1.0, 2.0, 3.0])
        b = array.array("f", [0.0, 0.0, 0.0])
        result = _dot_py(a, b)
        assert abs(result) < 1e-10


class TestRRFScore:
    """Tests for Reciprocal Rank Fusion scoring."""

    def test_rrf_both_ranks(self) -> None:
        """Test RRF with both semantic and FTS ranks."""
        # Standard k=60, ranks 1 and 1
        score = _rrf_score(1, 1, k=60)
        # 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.0328
        expected = 2.0 / 61.0
        assert abs(score - expected) < 1e-6

    def test_rrf_different_ranks(self) -> None:
        """Test RRF with different ranks."""
        # Rank 1 in semantic, rank 10 in FTS
        score = _rrf_score(1, 10, k=60)
        # 1/(60+1) + 1/(60+10) = 1/61 + 1/70
        expected = 1.0 / 61.0 + 1.0 / 70.0
        assert abs(score - expected) < 1e-6

    def test_rrf_semantic_only(self) -> None:
        """Test RRF with only semantic rank."""
        score = _rrf_score(5, None, k=60)
        # 1/(60+5) = 1/65
        expected = 1.0 / 65.0
        assert abs(score - expected) < 1e-6

    def test_rrf_fts_only(self) -> None:
        """Test RRF with only FTS rank."""
        score = _rrf_score(None, 3, k=60)
        # 1/(60+3) = 1/63
        expected = 1.0 / 63.0
        assert abs(score - expected) < 1e-6

    def test_rrf_neither_rank(self) -> None:
        """Test RRF with no ranks returns 0."""
        score = _rrf_score(None, None, k=60)
        assert score == 0.0

    def test_rrf_custom_k(self) -> None:
        """Test RRF with custom k value."""
        # k=30 should give higher scores
        score_k30 = _rrf_score(1, 1, k=30)
        score_k60 = _rrf_score(1, 1, k=60)
        # Higher k means lower scores for same ranks
        assert score_k30 > score_k60

    def test_rrf_rank_ordering(self) -> None:
        """Test RRF preserves rank ordering."""
        # Better ranks should give higher scores
        score_rank1 = _rrf_score(1, 1, k=60)
        score_rank5 = _rrf_score(5, 5, k=60)
        score_rank10 = _rrf_score(10, 10, k=60)
        assert score_rank1 > score_rank5 > score_rank10


class TestConfidenceScoring:
    """Tests for confidence level functions."""

    def test_absolute_confidence_ordering(self) -> None:
        """Test absolute confidence returns correct ordering."""
        # Test that higher scores produce equal or higher confidence
        # This tests the logic regardless of specific thresholds
        levels = ["very_low", "low", "medium", "high"]

        def level_rank(level: str) -> int:
            return levels.index(level)

        # Higher scores should have >= confidence
        assert level_rank(get_confidence_level(1.0)) >= level_rank(get_confidence_level(0.5))
        assert level_rank(get_confidence_level(0.5)) >= level_rank(get_confidence_level(0.3))
        assert level_rank(get_confidence_level(0.3)) >= level_rank(get_confidence_level(0.1))

    def test_absolute_confidence_extremes(self) -> None:
        """Test absolute confidence at extremes."""
        # Very high score should be "high"
        assert get_confidence_level(1.0) == "high"
        # Very low score should be "very_low"
        assert get_confidence_level(0.0) == "very_low"

    def test_absolute_confidence_valid_levels(self) -> None:
        """Test absolute confidence returns valid level strings."""
        valid_levels = {"high", "medium", "low", "very_low"}
        for score in [0.0, 0.25, 0.5, 0.75, 1.0]:
            assert get_confidence_level(score) in valid_levels

    def test_relative_confidence_high(self) -> None:
        """Test relative confidence for scores close to top."""
        # Default: >= 90% of top score is "high"
        assert get_relative_confidence(0.45, 0.45) == "high"  # 100%
        assert get_relative_confidence(0.42, 0.45) == "high"  # 93%
        assert get_relative_confidence(0.405, 0.45) == "high"  # 90%

    def test_relative_confidence_medium(self) -> None:
        """Test relative confidence for scores moderately close to top."""
        # Default: >= 75% of top score is "medium"
        assert get_relative_confidence(0.40, 0.45) == "medium"  # 89%
        assert get_relative_confidence(0.35, 0.45) == "medium"  # 78%
        assert get_relative_confidence(0.3375, 0.45) == "medium"  # 75%

    def test_relative_confidence_low(self) -> None:
        """Test relative confidence for scores around half of top."""
        # Default: >= 50% of top score is "low"
        assert get_relative_confidence(0.33, 0.45) == "low"  # 73%
        assert get_relative_confidence(0.25, 0.45) == "low"  # 56%
        assert get_relative_confidence(0.225, 0.45) == "low"  # 50%

    def test_relative_confidence_very_low(self) -> None:
        """Test relative confidence for scores much lower than top."""
        # Default: < 50% of top score is "very_low"
        assert get_relative_confidence(0.22, 0.45) == "very_low"  # 49%
        assert get_relative_confidence(0.10, 0.45) == "very_low"  # 22%

    def test_relative_confidence_zero_top_score(self) -> None:
        """Test relative confidence handles zero top score gracefully."""
        assert get_relative_confidence(0.0, 0.0) == "very_low"
        assert get_relative_confidence(0.5, 0.0) == "very_low"

    def test_assign_confidence_with_top_score(self) -> None:
        """Test assign_confidence returns hybrid confidence with top_score."""
        # When top_score is provided, returns (level, HybridConfidence)
        level, details = assign_confidence(0.42, top_score=0.45)
        # 0.42/0.45 = 93% >= 90% threshold = "high"
        assert level == "high"
        assert details is not None
        assert details.level == "high"
        assert details.relative_pct > 90  # 93.3%
        assert details.absolute_quality == "expected_range"  # 0.42 >= 0.35

    def test_assign_confidence_no_top_score(self) -> None:
        """Test assign_confidence without top_score falls back to absolute."""
        # Without top_score, should use absolute thresholds
        level, details = assign_confidence(0.45)
        # 0.45 >= 0.40 (medium threshold) but < 0.50 (high threshold) = "medium"
        assert level == "medium"
        # No details in absolute mode (legacy)
        assert details is None


class TestHybridConfidence:
    """Tests for hybrid confidence scoring.

    Hybrid confidence combines relative position (vs top score) with
    absolute quality bands to give AI tools actionable guidance.
    """

    def test_strong_top_result(self) -> None:
        """Test strong match at top position."""
        c = compute_hybrid_confidence(0.65, top_score=0.65, rank=1)
        assert c.level == "high"
        assert c.absolute_quality == "strong"
        assert c.signal == "top_result_strong_match"
        assert c.relative_pct == 100.0

    def test_expected_range_top_result(self) -> None:
        """Test typical good match at top position."""
        c = compute_hybrid_confidence(0.40, top_score=0.40, rank=1)
        assert c.level == "high"
        assert c.absolute_quality == "expected_range"
        assert c.signal == "top_result_in_typical_range"

    def test_weak_top_result(self) -> None:
        """Test weak match at top position."""
        c = compute_hybrid_confidence(0.28, top_score=0.28, rank=1)
        assert c.level == "medium"  # Still usable but cautious
        assert c.absolute_quality == "weak"
        assert c.signal == "top_result_weak_absolute"

    def test_very_weak_top_result(self) -> None:
        """Test very weak match at top - the key scenario.

        This is the case where correct results have low absolute scores.
        AI should know this is the best available, not distrust it.
        """
        c = compute_hybrid_confidence(0.03, top_score=0.03, rank=1)
        assert c.level == "medium"  # Not very_low!
        assert c.absolute_quality == "very_weak"
        assert c.signal == "top_result_very_weak_but_best_available"
        assert c.relative_pct == 100.0

    def test_close_to_top(self) -> None:
        """Test result that's close to top score."""
        c = compute_hybrid_confidence(0.60, top_score=0.65, rank=2)
        # 60/65 = 92% - close to top
        assert c.level == "high"
        assert c.signal == "close_to_top"
        assert c.relative_pct > 90

    def test_moderate_relevance(self) -> None:
        """Test result with moderate relevance."""
        c = compute_hybrid_confidence(0.35, top_score=0.65, rank=5)
        # 35/65 = 54% - moderate relative, but 0.35 is in "expected_range"
        # So it gets bumped to "medium" due to absolute quality
        assert c.level == "medium"
        assert c.absolute_quality == "expected_range"
        assert 50 < c.relative_pct < 75

    def test_score_drop_from_top(self) -> None:
        """Test result far below top score."""
        c = compute_hybrid_confidence(0.15, top_score=0.65, rank=10)
        # 15/65 = 23% - significant drop
        assert c.level == "very_low"
        assert c.signal == "score_drop_from_top"
        assert c.relative_pct < 50

    def test_to_dict(self) -> None:
        """Test HybridConfidence.to_dict() for JSON serialization."""
        c = compute_hybrid_confidence(0.50, top_score=0.55, rank=2)
        d = c.to_dict()
        assert "level" in d
        assert "relative_pct" in d
        assert "absolute_quality" in d
        assert "signal" in d
        assert isinstance(d["relative_pct"], float)

    def test_zero_top_score_edge_case(self) -> None:
        """Test handling of zero top score."""
        c = compute_hybrid_confidence(0.5, top_score=0.0, rank=1)
        assert c.level == "very_low"
        assert c.signal == "no_valid_top_score"


class TestAbsoluteQuality:
    """Tests for get_absolute_quality function."""

    def test_strong_threshold(self) -> None:
        """Test strong quality (>= 0.50)."""
        assert get_absolute_quality(0.50) == "strong"
        assert get_absolute_quality(0.65) == "strong"

    def test_expected_range_threshold(self) -> None:
        """Test expected_range quality (>= 0.35, < 0.50)."""
        assert get_absolute_quality(0.35) == "expected_range"
        assert get_absolute_quality(0.45) == "expected_range"
        assert get_absolute_quality(0.49) == "expected_range"

    def test_weak_threshold(self) -> None:
        """Test weak quality (>= 0.25, < 0.35)."""
        assert get_absolute_quality(0.25) == "weak"
        assert get_absolute_quality(0.30) == "weak"
        assert get_absolute_quality(0.34) == "weak"

    def test_very_weak_threshold(self) -> None:
        """Test very_weak quality (< 0.25)."""
        assert get_absolute_quality(0.24) == "very_weak"
        assert get_absolute_quality(0.10) == "very_weak"
        assert get_absolute_quality(0.03) == "very_weak"


class TestQuery:
    """Tests for query function."""

    def test_query_empty_database(self, temp_dir: Path) -> None:
        """Test query against empty database."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()

        hits, fts_available = query(db_path, "test query", top_k=5)
        assert hits == []

    def test_query_returns_hits(self, temp_dir: Path) -> None:
        """Test query returns Hit objects."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()
        con = connect(db_path)

        # Insert a test file and chunk
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test/file.py", 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create embedding for test chunk
        text = "def authenticate_user(username, password):"
        blobs, dim = embed_texts([text])

        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, 0, 1, 5, text, "hash123", blobs[0], dim, "text-embedding-3-small"),
        )
        con.commit()

        # Query
        hits, fts_available = query(db_path, "user authentication", top_k=5, branch="default")
        assert len(hits) == 1
        assert isinstance(hits[0], Hit)
        assert hits[0].path == "/test/file.py"
        assert hits[0].start_line == 1
        assert "authenticate" in hits[0].text

    def test_query_respects_top_k(self, temp_dir: Path) -> None:
        """Test that query respects top_k limit."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()
        con = connect(db_path)

        # Insert a test file
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test/file.py", 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert multiple chunks
        texts = [
            "def function_one(): pass",
            "def function_two(): pass",
            "def function_three(): pass",
            "def function_four(): pass",
            "def function_five(): pass",
        ]
        blobs, dim = embed_texts(texts)

        for i, (text, blob) in enumerate(zip(texts, blobs, strict=True)):
            con.execute(
                """INSERT INTO chunks
                   (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    file_id,
                    i,
                    i * 10,
                    i * 10 + 5,
                    text,
                    f"hash{i}",
                    blob,
                    dim,
                    "text-embedding-3-small",
                ),
            )
        con.commit()

        # Query with different top_k values
        hits_2, _ = query(db_path, "function", top_k=2, branch="default")
        hits_3, _ = query(db_path, "function", top_k=3, branch="default")
        hits_10, _ = query(db_path, "function", top_k=10, branch="default")

        assert len(hits_2) == 2
        assert len(hits_3) == 3
        assert len(hits_10) == 5  # Only 5 chunks in DB

    def test_query_sorted_by_score(self, temp_dir: Path) -> None:
        """Test that results are sorted by score descending."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()
        con = connect(db_path)

        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test/file.py", 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert chunks with different content
        texts = [
            "completely unrelated content xyz",
            "authentication login user password",  # More relevant
            "random text here",
        ]
        blobs, dim = embed_texts(texts)

        for i, (text, blob) in enumerate(zip(texts, blobs, strict=True)):
            con.execute(
                """INSERT INTO chunks
                   (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    file_id,
                    i,
                    i * 10,
                    i * 10 + 5,
                    text,
                    f"hash{i}",
                    blob,
                    dim,
                    "text-embedding-3-small",
                ),
            )
        con.commit()

        hits, _ = query(db_path, "user login authentication", top_k=10, branch="default")

        # Verify descending order
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)

    def test_query_dimension_mismatch_error(self, temp_dir: Path) -> None:
        """Test that dimension mismatch raises helpful error."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()
        con = connect(db_path)

        # Insert a file and chunk with specific dimensions
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test/file.py", 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create embedding with different dimension (768D for local model)
        # We'll manually create a different-sized embedding
        fake_embedding = array.array("f", [0.1] * 768).tobytes()

        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, 0, 1, 5, "test", "hash", fake_embedding, 768, "nomic-embed-text-v1.5"),
        )
        con.commit()

        # Query with different model (256D in mock)
        with pytest.raises(ValueError, match="Dimension mismatch"):
            query(db_path, "test", model="small")


class TestQueryScoring:
    """Tests for query scoring accuracy."""

    def test_identical_text_high_score(self, temp_dir: Path) -> None:
        """Test that identical text produces high similarity score."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()
        con = connect(db_path)

        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test/file.py", 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        text = "def process_payment(amount, currency):"
        blobs, dim = embed_texts([text])

        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, 0, 1, 5, text, "hash", blobs[0], dim, "text-embedding-3-small"),
        )
        con.commit()

        # Query with exact same text (use semantic mode to avoid FTS5 issues)
        hits, _ = query(db_path, text, top_k=1, mode="semantic", branch="default")
        assert len(hits) == 1
        # Score should be very high (close to 1.0) for identical text
        assert hits[0].score > 0.9

    def test_similar_text_reasonable_score(self, temp_dir: Path) -> None:
        """Test that similar text produces reasonable score."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()
        con = connect(db_path)

        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test/file.py", 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        text = "def connect_to_database(host, port, username):"
        blobs, dim = embed_texts([text])

        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, 0, 1, 5, text, "hash", blobs[0], dim, "text-embedding-3-small"),
        )
        con.commit()

        # Query with semantically similar text
        hits, _ = query(db_path, "database connection", top_k=1, branch="default")
        assert len(hits) == 1
        # Score should be positive for related concepts
        assert hits[0].score > 0


class TestConfidenceLevels:
    """Tests for confidence level calculation.

    Note: These tests use the actual threshold values from the module,
    which may be overridden by environment variables (OGREP_CONFIDENCE_*).
    """

    def test_get_confidence_level_high(self) -> None:
        """Test that scores at or above high threshold return 'high'."""
        from ogrep.search import CONFIDENCE_HIGH, get_confidence_level

        assert get_confidence_level(1.0) == "high"
        assert get_confidence_level(CONFIDENCE_HIGH) == "high"
        assert get_confidence_level(CONFIDENCE_HIGH + 0.05) == "high"

    def test_get_confidence_level_medium(self) -> None:
        """Test that scores between medium and high thresholds return 'medium'."""
        from ogrep.search import (
            CONFIDENCE_HIGH,
            CONFIDENCE_MEDIUM,
            get_confidence_level,
        )

        # Just below high threshold
        assert get_confidence_level(CONFIDENCE_HIGH - 0.01) == "medium"
        # At medium threshold
        assert get_confidence_level(CONFIDENCE_MEDIUM) == "medium"
        # Between medium and high
        mid_point = (CONFIDENCE_MEDIUM + CONFIDENCE_HIGH) / 2
        assert get_confidence_level(mid_point) == "medium"

    def test_get_confidence_level_low(self) -> None:
        """Test that scores between low and medium thresholds return 'low'."""
        from ogrep.search import (
            CONFIDENCE_LOW,
            CONFIDENCE_MEDIUM,
            get_confidence_level,
        )

        # Just below medium threshold
        assert get_confidence_level(CONFIDENCE_MEDIUM - 0.01) == "low"
        # At low threshold
        assert get_confidence_level(CONFIDENCE_LOW) == "low"
        # Between low and medium
        mid_point = (CONFIDENCE_LOW + CONFIDENCE_MEDIUM) / 2
        assert get_confidence_level(mid_point) == "low"

    def test_get_confidence_level_very_low(self) -> None:
        """Test that scores below low threshold return 'very_low'."""
        from ogrep.search import CONFIDENCE_LOW, get_confidence_level

        # Just below low threshold
        assert get_confidence_level(CONFIDENCE_LOW - 0.01) == "very_low"
        # Zero
        assert get_confidence_level(0.0) == "very_low"
        # Half the low threshold
        assert get_confidence_level(CONFIDENCE_LOW / 2) == "very_low"

    def test_query_returns_confidence(self, temp_dir: Path) -> None:
        """Test that query results include confidence level."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()
        con = connect(db_path)

        # Insert a test file and chunk
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test/file.py", 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create embedding for test chunk
        text = "def authenticate_user(username, password):"
        blobs, dim = embed_texts([text])

        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, 0, 1, 5, text, "hash123", blobs[0], dim, "text-embedding-3-small"),
        )
        con.commit()

        # Query
        hits, _ = query(db_path, "user authentication", top_k=5, branch="default")
        assert len(hits) == 1
        assert hasattr(hits[0], "confidence")
        assert hits[0].confidence in ("high", "medium", "low", "very_low")


class TestMixedDimensionsDetection:
    """Tests for detecting corrupted indexes with mixed dimensions."""

    def test_mixed_dimensions_raises_error(self, temp_dir: Path) -> None:
        """Test that query detects and reports mixed dimensions in index."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()
        con = connect(db_path)

        # Insert a test file
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test/file.py", 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert chunk with 768D (simulating nomic model)
        fake_768d = array.array("f", [0.1] * 768).tobytes()
        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, 0, 1, 5, "first chunk", "hash1", fake_768d, 768, "nomic"),
        )

        # Insert chunk with 1536D (simulating OpenAI model) - corruption!
        fake_1536d = array.array("f", [0.1] * 1536).tobytes()
        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                file_id,
                1,
                6,
                10,
                "second chunk",
                "hash2",
                fake_1536d,
                1536,
                "text-embedding-3-small",
            ),
        )
        con.commit()

        # Query should detect mixed dimensions and raise clear error
        with pytest.raises(ValueError, match="mixed dimensions"):
            query(db_path, "test", model="nomic")

    def test_consistent_dimensions_works(self, temp_dir: Path) -> None:
        """Test that consistent dimensions work normally."""
        db_path = temp_dir / "index.sqlite"
        connect(db_path).close()
        con = connect(db_path)

        # Insert a test file
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test/file.py", 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert two chunks with same dimensions (768D)
        fake_768d_1 = array.array("f", [0.1] * 768).tobytes()
        fake_768d_2 = array.array("f", [0.2] * 768).tobytes()

        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, 0, 1, 5, "first chunk", "hash1", fake_768d_1, 768, "nomic"),
        )
        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, 1, 6, 10, "second chunk", "hash2", fake_768d_2, 768, "nomic"),
        )
        con.commit()

        # Should work fine - no mixed dimensions
        # Note: Will fail on dimension mismatch with mock, but NOT on mixed dimensions
        try:
            query(db_path, "test", model="nomic")
        except ValueError as e:
            # Should NOT be a "mixed dimensions" error
            assert "mixed dimensions" not in str(e).lower()


# =============================================================================
# Path Filtering Tests
# =============================================================================


class TestPathFilter:
    """Tests for PathFilter dataclass."""

    def test_empty_filter(self) -> None:
        """Test that empty filter is detected."""
        pf = PathFilter()
        assert pf.is_empty()

    def test_filter_with_glob(self) -> None:
        """Test filter with glob patterns is not empty."""
        pf = PathFilter(glob_patterns=["*.py"])
        assert not pf.is_empty()

    def test_filter_with_exclude(self) -> None:
        """Test filter with exclude patterns is not empty."""
        pf = PathFilter(exclude_patterns=["tests/*"])
        assert not pf.is_empty()

    def test_filter_with_both(self) -> None:
        """Test filter with both glob and exclude is not empty."""
        pf = PathFilter(glob_patterns=["*.py"], exclude_patterns=["tests/*"])
        assert not pf.is_empty()


class TestIsSimplePattern:
    """Tests for is_simple_pattern function."""

    def test_simple_extension_pattern(self) -> None:
        """Test *.py is simple."""
        assert is_simple_pattern("*.py")

    def test_simple_directory_pattern(self) -> None:
        """Test src/* is simple."""
        assert is_simple_pattern("src/*")

    def test_simple_mixed_pattern(self) -> None:
        """Test templates/*.j2 is simple."""
        assert is_simple_pattern("templates/*.j2")

    def test_recursive_pattern_not_simple(self) -> None:
        """Test **/*.py is not simple (recursive)."""
        assert not is_simple_pattern("**/*.py")

    def test_deeply_recursive_pattern_not_simple(self) -> None:
        """Test src/**/*.j2 is not simple."""
        assert not is_simple_pattern("src/**/*.j2")

    def test_brace_expansion_not_simple(self) -> None:
        """Test brace expansion is not simple."""
        assert not is_simple_pattern("*.{py,php}")


class TestMatchesAnyPattern:
    """Tests for matches_any_pattern function."""

    def test_simple_extension_match(self) -> None:
        """Test matching extension pattern."""
        assert matches_any_pattern("file.py", ["*.py"])
        assert not matches_any_pattern("file.js", ["*.py"])

    def test_multiple_patterns(self) -> None:
        """Test matching against multiple patterns."""
        patterns = ["*.py", "*.js"]
        assert matches_any_pattern("app.py", patterns)
        assert matches_any_pattern("app.js", patterns)
        assert not matches_any_pattern("app.go", patterns)

    def test_directory_pattern(self) -> None:
        """Test matching directory patterns."""
        assert matches_any_pattern("src/file.py", ["src/*"])
        assert not matches_any_pattern("tests/file.py", ["src/*"])

    def test_recursive_pattern(self) -> None:
        """Test matching recursive ** patterns."""
        assert matches_any_pattern("src/deep/nested/file.py", ["**/*.py"])
        assert matches_any_pattern("file.py", ["**/*.py"])

    def test_recursive_in_directory(self) -> None:
        """Test matching ** in subdirectory."""
        assert matches_any_pattern("src/a/b/c.py", ["src/**/*.py"])
        assert not matches_any_pattern("other/a/b/c.py", ["src/**/*.py"])

    def test_no_patterns_returns_false(self) -> None:
        """Test empty patterns returns False."""
        assert not matches_any_pattern("file.py", [])


class TestFilterStats:
    """Tests for FilterStats dataclass."""

    def test_to_dict(self) -> None:
        """Test converting FilterStats to dictionary."""
        stats = FilterStats(
            candidates_before=100,
            candidates_after=30,
            removal_pct=70.0,
            method="fnmatch_postfilter",
            warning="Filter removed too many results.",
        )
        d = stats.to_dict()
        assert d["candidates_before"] == 100
        assert d["candidates_after"] == 30
        assert d["removal_pct"] == 70.0
        assert d["method"] == "fnmatch_postfilter"
        assert d["warning"] == "Filter removed too many results."

    def test_to_dict_no_warning(self) -> None:
        """Test converting FilterStats without warning."""
        stats = FilterStats(
            candidates_before=10,
            candidates_after=8,
            removal_pct=20.0,
            method="none",
        )
        d = stats.to_dict()
        assert d["warning"] is None


class TestFilterHitsByPath:
    """Tests for filter_hits_by_path function."""

    def _make_hit(self, path: str, score: float = 0.5) -> Hit:
        """Helper to create a Hit with given path."""
        return Hit(
            score=score,
            path=path,
            start_line=1,
            end_line=10,
            text="test content",
            chunk_id=1,
            chunk_index=0,
            confidence="medium",
        )

    def test_empty_filter_passes_all(self) -> None:
        """Test empty filter passes all hits through."""
        hits = [
            self._make_hit("/src/app.py"),
            self._make_hit("/tests/test_app.py"),
        ]
        pf = PathFilter()
        filtered, stats = filter_hits_by_path(hits, pf, requested_n=10)
        assert len(filtered) == 2
        assert stats.method == "none"
        assert stats.removal_pct == 0.0

    def test_glob_filters_by_extension(self) -> None:
        """Test glob pattern filters by file extension."""
        hits = [
            self._make_hit("/src/app.py"),
            self._make_hit("/src/styles.css"),
            self._make_hit("/src/utils.py"),
        ]
        pf = PathFilter(glob_patterns=["*.py"])
        filtered, stats = filter_hits_by_path(hits, pf, requested_n=10)
        assert len(filtered) == 2
        assert all("py" in h.path for h in filtered)
        assert stats.method == "fnmatch_postfilter"

    def test_exclude_removes_matching_files(self) -> None:
        """Test exclude patterns remove matching files."""
        hits = [
            self._make_hit("/src/app.py"),
            self._make_hit("/tests/test_app.py"),
            self._make_hit("/tests/test_utils.py"),
        ]
        pf = PathFilter(exclude_patterns=["tests/*"])
        filtered, stats = filter_hits_by_path(hits, pf, requested_n=10)
        assert len(filtered) == 1
        assert filtered[0].path == "/src/app.py"

    def test_combined_glob_and_exclude(self) -> None:
        """Test combining glob and exclude patterns."""
        hits = [
            self._make_hit("/src/app.py"),
            self._make_hit("/src/config.py"),
            self._make_hit("/tests/test_app.py"),
            self._make_hit("/src/styles.css"),
        ]
        pf = PathFilter(glob_patterns=["*.py"], exclude_patterns=["tests/*"])
        filtered, stats = filter_hits_by_path(hits, pf, requested_n=10)
        assert len(filtered) == 2
        assert all("src" in h.path and h.path.endswith(".py") for h in filtered)

    def test_warning_when_many_removed(self) -> None:
        """Test warning is generated when >50% results removed."""
        hits = [
            self._make_hit("/src/app.py"),
            self._make_hit("/src/style1.css"),
            self._make_hit("/src/style2.css"),
            self._make_hit("/src/style3.css"),
        ]
        pf = PathFilter(glob_patterns=["*.py"])
        filtered, stats = filter_hits_by_path(hits, pf, requested_n=10)
        assert len(filtered) == 1
        assert stats.warning is not None
        assert "75" in str(stats.removal_pct) or stats.removal_pct == 75.0

    def test_no_warning_when_few_removed(self) -> None:
        """Test no warning when <50% results removed."""
        hits = [
            self._make_hit("/src/app.py"),
            self._make_hit("/src/utils.py"),
            self._make_hit("/src/models.py"),
            self._make_hit("/src/style.css"),
        ]
        pf = PathFilter(glob_patterns=["*.py"])
        filtered, stats = filter_hits_by_path(hits, pf, requested_n=10)
        assert len(filtered) == 3
        assert stats.warning is None

    def test_preserves_order(self) -> None:
        """Test filtering preserves hit order."""
        hits = [
            self._make_hit("/src/a.py", score=0.9),
            self._make_hit("/src/b.css", score=0.8),
            self._make_hit("/src/c.py", score=0.7),
        ]
        pf = PathFilter(glob_patterns=["*.py"])
        filtered, _ = filter_hits_by_path(hits, pf, requested_n=10)
        assert len(filtered) == 2
        assert filtered[0].path == "/src/a.py"
        assert filtered[1].path == "/src/c.py"
        assert filtered[0].score > filtered[1].score
