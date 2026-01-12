"""Tests for ogrep.search module."""

from __future__ import annotations

import array
from pathlib import Path

import pytest

from ogrep.db import connect
from ogrep.embed import embed_texts
from ogrep.search import Hit, _dot_py, query


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
        hits, fts_available = query(db_path, "user authentication", top_k=5)
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
        hits_2, _ = query(db_path, "function", top_k=2)
        hits_3, _ = query(db_path, "function", top_k=3)
        hits_10, _ = query(db_path, "function", top_k=10)

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

        hits, _ = query(db_path, "user login authentication", top_k=10)

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
        hits, _ = query(db_path, text, top_k=1, mode="semantic")
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
        hits, _ = query(db_path, "database connection", top_k=1)
        assert len(hits) == 1
        # Score should be positive for related concepts
        assert hits[0].score > 0


class TestConfidenceLevels:
    """Tests for confidence level calculation."""

    def test_get_confidence_level_high(self) -> None:
        """Test that high scores return 'high' confidence."""
        from ogrep.search import get_confidence_level

        assert get_confidence_level(0.95) == "high"
        assert get_confidence_level(0.85) == "high"
        assert get_confidence_level(1.0) == "high"

    def test_get_confidence_level_medium(self) -> None:
        """Test that medium scores return 'medium' confidence."""
        from ogrep.search import get_confidence_level

        assert get_confidence_level(0.84) == "medium"
        assert get_confidence_level(0.75) == "medium"
        assert get_confidence_level(0.70) == "medium"

    def test_get_confidence_level_low(self) -> None:
        """Test that low scores return 'low' confidence."""
        from ogrep.search import get_confidence_level

        assert get_confidence_level(0.69) == "low"
        assert get_confidence_level(0.55) == "low"
        assert get_confidence_level(0.50) == "low"

    def test_get_confidence_level_very_low(self) -> None:
        """Test that very low scores return 'very_low' confidence."""
        from ogrep.search import get_confidence_level

        assert get_confidence_level(0.49) == "very_low"
        assert get_confidence_level(0.25) == "very_low"
        assert get_confidence_level(0.0) == "very_low"

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
        hits, _ = query(db_path, "user authentication", top_k=5)
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
