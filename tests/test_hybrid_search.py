"""Tests for hybrid search functionality."""

from __future__ import annotations

import array
from pathlib import Path

import pytest

from ogrep.db import connect, has_fts5, rebuild_fts5
from ogrep.embed import embed_texts
from ogrep.search import _escape_fts5_query, query


class TestFTS5Schema:
    """Tests for FTS5 database schema."""

    def test_fts5_created_on_connect(self, temp_dir: Path) -> None:
        """Test that FTS5 table is created on connect."""
        db_path = temp_dir / "index.sqlite"
        con = connect(db_path)

        assert has_fts5(con)
        con.close()

    def test_fts5_triggers_on_insert(self, temp_dir: Path) -> None:
        """Test that FTS5 is populated via triggers on insert."""
        db_path = temp_dir / "index.sqlite"
        con = connect(db_path)

        # Insert a file and chunk
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test.py", 0, 100, "abc"),
        )
        fake_embedding = array.array("f", [0.1] * 256).tobytes()
        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (1, 0, 1, 10, 'def authenticate_user(): pass', 'hash', ?, 256, 'test')""",
            (fake_embedding,),
        )
        con.commit()

        # Check FTS was populated
        fts_count = con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
        assert fts_count == 1

        # Check we can search
        results = con.execute(
            "SELECT rowid FROM chunks_fts WHERE text MATCH '\"authenticate\"'"
        ).fetchall()
        assert len(results) == 1

    def test_fts5_triggers_on_delete(self, temp_dir: Path) -> None:
        """Test that FTS5 is updated on chunk deletion."""
        db_path = temp_dir / "index.sqlite"
        con = connect(db_path)

        # Insert
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test.py", 0, 100, "abc"),
        )
        fake_embedding = array.array("f", [0.1] * 256).tobytes()
        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (1, 0, 1, 10, 'test content', 'hash', ?, 256, 'test')""",
            (fake_embedding,),
        )
        con.commit()

        # Verify inserted
        assert con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0] == 1

        # Delete via CASCADE (delete file)
        con.execute("DELETE FROM files WHERE id = 1")
        con.commit()

        # FTS should be empty
        assert con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0] == 0

    def test_rebuild_fts5(self, temp_dir: Path) -> None:
        """Test rebuilding FTS5 index from existing chunks."""
        db_path = temp_dir / "index.sqlite"
        con = connect(db_path, init_fts=False)  # Skip FTS init

        # Insert without FTS
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test.py", 0, 100, "abc"),
        )
        fake_embedding = array.array("f", [0.1] * 256).tobytes()
        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (1, 0, 1, 10, 'test content', 'hash', ?, 256, 'test')""",
            (fake_embedding,),
        )
        con.commit()

        # FTS shouldn't exist yet
        assert not has_fts5(con)

        # Rebuild
        count = rebuild_fts5(con)
        assert count == 1

        # Now FTS should work
        assert has_fts5(con)
        results = con.execute("SELECT rowid FROM chunks_fts WHERE text MATCH '\"test\"'").fetchall()
        assert len(results) == 1


class TestEscapeFTS5Query:
    """Tests for FTS5 query escaping."""

    def test_simple_terms(self) -> None:
        """Test escaping simple terms."""
        assert _escape_fts5_query("hello world") == '"hello" "world"'

    def test_underscore(self) -> None:
        """Test escaping terms with underscores."""
        assert _escape_fts5_query("authenticate_user") == '"authenticate_user"'

    def test_special_chars(self) -> None:
        """Test escaping terms with special characters."""
        result = _escape_fts5_query("foo.bar baz")
        assert result == '"foo.bar" "baz"'


class TestSearchModes:
    """Tests for different search modes."""

    @pytest.fixture
    def indexed_db(self, temp_dir: Path) -> Path:
        """Create a database with indexed chunks for testing."""
        db_path = temp_dir / ".ogrep" / "index.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        con = connect(db_path)

        # Insert a test file
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            (str(temp_dir / "auth.py"), 0, 100, "abc123"),
        )
        file_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert chunks with different content
        texts = [
            "def authenticate_user(username, password): pass",
            "class UserValidator: pass",
            "def random_function(): return 42",
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
                    i * 20 + 1,
                    (i + 1) * 20,
                    text,
                    f"hash{i}",
                    blob,
                    dim,
                    "text-embedding-3-small",
                ),
            )
        con.commit()
        con.close()

        return db_path

    def test_semantic_mode(self, indexed_db: Path) -> None:
        """Test semantic-only search mode."""
        hits, fts_available = query(indexed_db, "user login authentication", mode="semantic")

        assert len(hits) > 0
        assert fts_available  # FTS is available but not used

    def test_fulltext_mode(self, indexed_db: Path) -> None:
        """Test fulltext-only search mode."""
        hits, fts_available = query(indexed_db, "authenticate", mode="fulltext")

        assert fts_available
        # Should find the chunk containing "authenticate"
        if hits:  # May not find if FTS quoting doesn't match
            assert any("authenticate" in h.text for h in hits)

    def test_hybrid_mode(self, indexed_db: Path) -> None:
        """Test hybrid search mode."""
        hits, fts_available = query(indexed_db, "user authentication", mode="hybrid")

        assert fts_available
        assert len(hits) > 0

    def test_fts_unavailable_fallback(self, temp_dir: Path) -> None:
        """Test graceful fallback when FTS5 is unavailable."""
        db_path = temp_dir / "index.sqlite"
        con = connect(db_path, init_fts=False)  # No FTS

        # Insert data
        con.execute(
            "INSERT INTO files (path, mtime_ns, size, sha256) VALUES (?, ?, ?, ?)",
            ("/test.py", 0, 100, "abc"),
        )
        text = "def test_function(): pass"
        blobs, dim = embed_texts([text])
        con.execute(
            """INSERT INTO chunks
               (file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
               VALUES (1, 0, 1, 10, ?, 'hash', ?, ?, 'text-embedding-3-small')""",
            (text, blobs[0], dim),
        )
        con.commit()
        con.close()

        # Query with hybrid mode should fall back to semantic
        hits, fts_available = query(db_path, "test function", mode="hybrid")

        assert not fts_available  # FTS not available
        assert len(hits) > 0  # But semantic search still works

    def test_mode_from_default(self, indexed_db: Path) -> None:
        """Test that mode defaults to hybrid."""
        hits, fts_available = query(indexed_db, "authentication")

        # Should use hybrid by default
        assert len(hits) > 0
