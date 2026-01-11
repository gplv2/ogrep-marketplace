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
        )
        assert hit.score == 0.95
        assert hit.path == "/path/to/file.py"
        assert hit.start_line == 10
        assert hit.end_line == 20
        assert "hello" in hit.text

    def test_hit_is_frozen(self) -> None:
        """Test that Hit is immutable."""
        hit = Hit(score=0.5, path="/test.py", start_line=1, end_line=5, text="test")
        with pytest.raises(AttributeError):  # Frozen dataclass
            hit.score = 0.9  # type: ignore[misc]

    def test_hit_comparison(self) -> None:
        """Test that hits with same values are equal."""
        hit1 = Hit(score=0.5, path="/test.py", start_line=1, end_line=5, text="test")
        hit2 = Hit(score=0.5, path="/test.py", start_line=1, end_line=5, text="test")
        assert hit1 == hit2

    def test_hit_different_scores(self) -> None:
        """Test that hits with different scores are not equal."""
        hit1 = Hit(score=0.5, path="/test.py", start_line=1, end_line=5, text="test")
        hit2 = Hit(score=0.6, path="/test.py", start_line=1, end_line=5, text="test")
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

        hits = query(db_path, "test query", top_k=5)
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
        hits = query(db_path, "user authentication", top_k=5)
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
        hits_2 = query(db_path, "function", top_k=2)
        hits_3 = query(db_path, "function", top_k=3)
        hits_10 = query(db_path, "function", top_k=10)

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

        hits = query(db_path, "user login authentication", top_k=10)

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

        # Query with exact same text
        hits = query(db_path, text, top_k=1)
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
        hits = query(db_path, "database connection", top_k=1)
        assert len(hits) == 1
        # Score should be positive for related concepts
        assert hits[0].score > 0
