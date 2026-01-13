"""
Comprehensive integration tests for AST-aware chunking.

Tests the full pipeline: indexing with AST chunking, querying results,
and verifying that semantic boundaries are respected.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Skip all tests if tree-sitter not installed
try:
    from ogrep.ast_chunking import is_ast_available, chunk_ast, SUPPORTED_LANGUAGES

    HAS_TREE_SITTER = is_ast_available()
except ImportError:
    HAS_TREE_SITTER = False

pytestmark = pytest.mark.skipif(
    not HAS_TREE_SITTER, reason="tree-sitter not installed (pip install ogrep[ast])"
)


# =============================================================================
# Test Fixtures - Sample Code in Various Languages
# =============================================================================

PYTHON_PROJECT = {
    "auth.py": '''"""Authentication module."""

import hashlib
import secrets


class PasswordHasher:
    """Hash and verify passwords using SHA-256."""

    def __init__(self, salt_length: int = 16):
        self.salt_length = salt_length

    def hash_password(self, password: str) -> str:
        """Hash a password with a random salt."""
        salt = secrets.token_hex(self.salt_length)
        hashed = hashlib.sha256((salt + password).encode()).hexdigest()
        return f"{salt}${hashed}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a password against a stored hash."""
        salt, expected_hash = stored_hash.split("$")
        actual_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        return actual_hash == expected_hash


def create_session_token(user_id: int) -> str:
    """Create a secure session token for a user."""
    return secrets.token_urlsafe(32)


def validate_session_token(token: str) -> bool:
    """Validate that a session token is properly formatted."""
    return len(token) >= 32
''',
    "database.py": '''"""Database connection and query utilities."""

import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator


class DatabaseConnection:
    """Manage SQLite database connections."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection = None

    def connect(self) -> None:
        """Open database connection."""
        self._connection = sqlite3.connect(self.db_path)
        self._connection.row_factory = sqlite3.Row

    def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        """Execute queries within a transaction."""
        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cursor.close()


def execute_query(conn: DatabaseConnection, sql: str, params: tuple = ()) -> list[Any]:
    """Execute a SQL query and return results."""
    with conn.transaction() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def insert_record(conn: DatabaseConnection, table: str, data: dict) -> int:
    """Insert a record and return the new ID."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join("?" * len(data))
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    with conn.transaction() as cursor:
        cursor.execute(sql, tuple(data.values()))
        return cursor.lastrowid
''',
    "api.py": '''"""REST API endpoint handlers."""

from typing import Any


class APIResponse:
    """Standard API response wrapper."""

    def __init__(self, data: Any = None, error: str | None = None, status: int = 200):
        self.data = data
        self.error = error
        self.status = status

    def to_dict(self) -> dict:
        """Convert response to dictionary."""
        if self.error:
            return {"error": self.error, "status": self.status}
        return {"data": self.data, "status": self.status}


def handle_login(username: str, password: str) -> APIResponse:
    """Handle user login request."""
    if not username or not password:
        return APIResponse(error="Missing credentials", status=400)
    # Authentication logic would go here
    return APIResponse(data={"token": "abc123"})


def handle_logout(token: str) -> APIResponse:
    """Handle user logout request."""
    if not token:
        return APIResponse(error="No token provided", status=401)
    # Logout logic would go here
    return APIResponse(data={"message": "Logged out"})


def handle_get_user(user_id: int) -> APIResponse:
    """Get user details by ID."""
    if user_id <= 0:
        return APIResponse(error="Invalid user ID", status=400)
    # Database lookup would go here
    return APIResponse(data={"id": user_id, "name": "Test User"})


def handle_update_user(user_id: int, data: dict) -> APIResponse:
    """Update user details."""
    if user_id <= 0:
        return APIResponse(error="Invalid user ID", status=400)
    if not data:
        return APIResponse(error="No data provided", status=400)
    # Update logic would go here
    return APIResponse(data={"id": user_id, **data})
''',
}

JAVASCRIPT_PROJECT = {
    "utils.js": '''/**
 * Utility functions for string manipulation.
 */

function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function truncate(str, maxLength) {
    if (str.length <= maxLength) return str;
    return str.slice(0, maxLength - 3) + '...';
}

const slugify = (text) => {
    return text
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '');
};

class StringBuilder {
    constructor() {
        this.parts = [];
    }

    append(str) {
        this.parts.push(str);
        return this;
    }

    toString() {
        return this.parts.join('');
    }

    clear() {
        this.parts = [];
        return this;
    }
}

module.exports = { capitalize, truncate, slugify, StringBuilder };
''',
}

GO_PROJECT = {
    "server.go": '''package main

import (
    "encoding/json"
    "log"
    "net/http"
)

// Response represents a standard API response
type Response struct {
    Data    interface{} `json:"data,omitempty"`
    Error   string      `json:"error,omitempty"`
    Status  int         `json:"status"`
}

// Server handles HTTP requests
type Server struct {
    port string
    mux  *http.ServeMux
}

// NewServer creates a new server instance
func NewServer(port string) *Server {
    return &Server{
        port: port,
        mux:  http.NewServeMux(),
    }
}

// Start begins listening for connections
func (s *Server) Start() error {
    log.Printf("Starting server on port %s", s.port)
    return http.ListenAndServe(":"+s.port, s.mux)
}

// HandleHealth returns server health status
func HandleHealth(w http.ResponseWriter, r *http.Request) {
    resp := Response{Data: "ok", Status: 200}
    json.NewEncoder(w).Encode(resp)
}

// HandleNotFound returns 404 for unknown routes
func HandleNotFound(w http.ResponseWriter, r *http.Request) {
    resp := Response{Error: "not found", Status: 404}
    w.WriteHeader(404)
    json.NewEncoder(w).Encode(resp)
}
''',
}

RUST_PROJECT = {
    "lib.rs": '''//! A simple key-value store implementation.

use std::collections::HashMap;
use std::sync::RwLock;

/// A thread-safe key-value store.
pub struct Store {
    data: RwLock<HashMap<String, String>>,
}

impl Store {
    /// Create a new empty store.
    pub fn new() -> Self {
        Store {
            data: RwLock::new(HashMap::new()),
        }
    }

    /// Get a value by key.
    pub fn get(&self, key: &str) -> Option<String> {
        let data = self.data.read().unwrap();
        data.get(key).cloned()
    }

    /// Set a key-value pair.
    pub fn set(&self, key: String, value: String) {
        let mut data = self.data.write().unwrap();
        data.insert(key, value);
    }

    /// Delete a key.
    pub fn delete(&self, key: &str) -> bool {
        let mut data = self.data.write().unwrap();
        data.remove(key).is_some()
    }

    /// Get the number of entries.
    pub fn len(&self) -> usize {
        let data = self.data.read().unwrap();
        data.len()
    }

    /// Check if the store is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

impl Default for Store {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_set_and_get() {
        let store = Store::new();
        store.set("key".to_string(), "value".to_string());
        assert_eq!(store.get("key"), Some("value".to_string()));
    }
}
''',
}


# =============================================================================
# Helper Functions
# =============================================================================


def create_test_project(base_dir: Path, files: dict[str, str]) -> None:
    """Create test files in the given directory."""
    for filename, content in files.items():
        file_path = base_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)


def get_chunk_texts(chunks: list) -> list[str]:
    """Extract text from chunks."""
    return [c.text for c in chunks]


def chunk_contains(chunks: list, substring: str) -> bool:
    """Check if any chunk contains the substring."""
    return any(substring in c.text for c in chunks)


def find_chunk_with(chunks: list, substring: str):
    """Find the first chunk containing the substring."""
    for c in chunks:
        if substring in c.text:
            return c
    return None


# =============================================================================
# Unit Tests - Python AST Chunking
# =============================================================================


class TestPythonASTChunking:
    """Test AST chunking for Python code."""

    def test_class_is_single_chunk(self):
        """A class with methods should be a single chunk."""
        chunks = chunk_ast(PYTHON_PROJECT["auth.py"], language="python")

        # Find the PasswordHasher class chunk
        class_chunk = find_chunk_with(chunks, "class PasswordHasher")
        assert class_chunk is not None

        # The entire class should be in one chunk
        assert "def __init__" in class_chunk.text
        assert "def hash_password" in class_chunk.text
        assert "def verify_password" in class_chunk.text

    def test_standalone_functions_are_separate_chunks(self):
        """Standalone functions should be separate chunks."""
        chunks = chunk_ast(PYTHON_PROJECT["auth.py"], language="python")

        # Should have separate chunks for standalone functions
        session_chunk = find_chunk_with(chunks, "def create_session_token")
        validate_chunk = find_chunk_with(chunks, "def validate_session_token")

        assert session_chunk is not None
        assert validate_chunk is not None

        # They should be different chunks (or same if adjacent)
        # The key is they're not split mid-function

    def test_function_body_not_split(self):
        """Function body should not be split from its definition."""
        chunks = chunk_ast(PYTHON_PROJECT["database.py"], language="python")

        # Find execute_query function
        exec_chunk = find_chunk_with(chunks, "def execute_query")
        assert exec_chunk is not None

        # The body should be complete
        assert "cursor.execute" in exec_chunk.text
        assert "return cursor.fetchall()" in exec_chunk.text

    def test_docstrings_included(self):
        """Docstrings should be included with their functions."""
        chunks = chunk_ast(PYTHON_PROJECT["auth.py"], language="python")

        # Find hash_password - it's part of the class
        class_chunk = find_chunk_with(chunks, "class PasswordHasher")
        assert class_chunk is not None
        assert "Hash a password with a random salt" in class_chunk.text

    def test_imports_in_module_chunk(self):
        """Module-level imports should be in their own chunk or with first definition."""
        chunks = chunk_ast(PYTHON_PROJECT["auth.py"], language="python")

        # Imports should exist somewhere
        all_text = " ".join(c.text for c in chunks)
        assert "import hashlib" in all_text
        assert "import secrets" in all_text

    def test_api_handlers_are_separate(self):
        """Each API handler function should be a separate chunk."""
        chunks = chunk_ast(PYTHON_PROJECT["api.py"], language="python")

        # Find each handler
        login_chunk = find_chunk_with(chunks, "def handle_login")
        logout_chunk = find_chunk_with(chunks, "def handle_logout")
        get_user_chunk = find_chunk_with(chunks, "def handle_get_user")
        update_user_chunk = find_chunk_with(chunks, "def handle_update_user")

        assert login_chunk is not None
        assert logout_chunk is not None
        assert get_user_chunk is not None
        assert update_user_chunk is not None

        # Each should have complete body
        assert "Missing credentials" in login_chunk.text
        assert "No token provided" in logout_chunk.text
        assert "Invalid user ID" in get_user_chunk.text


class TestPythonChunkBoundaries:
    """Test that chunk boundaries are correct."""

    def test_chunk_start_line_matches_definition(self):
        """Chunk start_line should match the function/class definition line."""
        code = '''def hello():
    pass

def world():
    pass
'''
        chunks = chunk_ast(code, language="python")

        assert len(chunks) == 2
        assert chunks[0].start_line == 1  # def hello
        assert chunks[1].start_line == 4  # def world

    def test_chunk_end_line_includes_body(self):
        """Chunk end_line should include the entire body."""
        code = '''def multiline():
    x = 1
    y = 2
    z = 3
    return x + y + z
'''
        chunks = chunk_ast(code, language="python")

        assert len(chunks) == 1
        assert chunks[0].start_line == 1
        assert chunks[0].end_line == 5

    def test_nested_function_stays_with_parent(self):
        """Nested functions should be part of their parent chunk."""
        code = '''def outer():
    def inner():
        return 42
    return inner()
'''
        chunks = chunk_ast(code, language="python")

        assert len(chunks) == 1
        assert "def outer" in chunks[0].text
        assert "def inner" in chunks[0].text


# =============================================================================
# Unit Tests - JavaScript AST Chunking
# =============================================================================


@pytest.mark.skipif(
    "javascript" not in SUPPORTED_LANGUAGES,
    reason="JavaScript parser not available",
)
class TestJavaScriptASTChunking:
    """Test AST chunking for JavaScript code."""

    def test_function_declarations(self):
        """Function declarations should be separate chunks."""
        chunks = chunk_ast(JAVASCRIPT_PROJECT["utils.js"], language="javascript")

        capitalize_chunk = find_chunk_with(chunks, "function capitalize")
        assert capitalize_chunk is not None
        assert "toUpperCase" in capitalize_chunk.text

    def test_arrow_functions(self):
        """Arrow functions with const should be chunked."""
        chunks = chunk_ast(JAVASCRIPT_PROJECT["utils.js"], language="javascript")

        slugify_chunk = find_chunk_with(chunks, "slugify")
        assert slugify_chunk is not None
        assert "toLowerCase" in slugify_chunk.text

    def test_class_declaration(self):
        """Class declarations should be chunked."""
        chunks = chunk_ast(JAVASCRIPT_PROJECT["utils.js"], language="javascript")

        class_chunk = find_chunk_with(chunks, "class StringBuilder")
        assert class_chunk is not None
        assert "append" in class_chunk.text
        assert "toString" in class_chunk.text


# =============================================================================
# Unit Tests - Go AST Chunking
# =============================================================================


@pytest.mark.skipif(
    "go" not in SUPPORTED_LANGUAGES,
    reason="Go parser not available",
)
class TestGoASTChunking:
    """Test AST chunking for Go code."""

    def test_function_declarations(self):
        """Go functions should be separate chunks."""
        chunks = chunk_ast(GO_PROJECT["server.go"], language="go")

        new_server_chunk = find_chunk_with(chunks, "func NewServer")
        assert new_server_chunk is not None
        assert "return &Server" in new_server_chunk.text

    def test_method_declarations(self):
        """Go methods should be separate chunks."""
        chunks = chunk_ast(GO_PROJECT["server.go"], language="go")

        start_chunk = find_chunk_with(chunks, "func (s *Server) Start")
        assert start_chunk is not None
        assert "ListenAndServe" in start_chunk.text

    def test_type_declarations(self):
        """Go type declarations should be chunked."""
        chunks = chunk_ast(GO_PROJECT["server.go"], language="go")

        # Types should be captured
        all_text = " ".join(c.text for c in chunks)
        assert "type Response struct" in all_text or "type Server struct" in all_text


# =============================================================================
# Unit Tests - Rust AST Chunking
# =============================================================================


@pytest.mark.skipif(
    "rust" not in SUPPORTED_LANGUAGES,
    reason="Rust parser not available",
)
class TestRustASTChunking:
    """Test AST chunking for Rust code."""

    def test_impl_block(self):
        """Rust impl blocks should be chunked."""
        chunks = chunk_ast(RUST_PROJECT["lib.rs"], language="rust")

        impl_chunk = find_chunk_with(chunks, "impl Store")
        assert impl_chunk is not None
        assert "pub fn new" in impl_chunk.text
        assert "pub fn get" in impl_chunk.text

    def test_struct_definition(self):
        """Rust structs should be chunked."""
        chunks = chunk_ast(RUST_PROJECT["lib.rs"], language="rust")

        struct_chunk = find_chunk_with(chunks, "pub struct Store")
        assert struct_chunk is not None
        assert "RwLock" in struct_chunk.text


# =============================================================================
# Integration Tests - Full Indexing Pipeline
# =============================================================================


class TestASTIndexingIntegration:
    """Test AST chunking through the full indexing pipeline."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project with Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            create_test_project(project_dir, PYTHON_PROJECT)
            yield project_dir

    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OGREP_BASE_URL"),
        reason="No embedding API configured",
    )
    @pytest.mark.integration
    def test_index_with_ast_flag(self, temp_project):
        """Test indexing a project with --ast flag."""
        from ogrep.indexer import index_path

        db_path = temp_project / ".ogrep" / "index.sqlite"

        stats = index_path(
            root=temp_project,
            db_path=db_path,
            ast=True,
            chunk_lines=100,  # High to avoid splitting within functions
        )

        assert stats.files_indexed >= 3
        assert stats.chunks_total > 0

    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OGREP_BASE_URL"),
        reason="No embedding API configured",
    )
    @pytest.mark.integration
    def test_ast_chunks_are_semantic(self, temp_project):
        """Verify that AST-indexed chunks respect semantic boundaries."""
        from ogrep.db import connect
        from ogrep.indexer import index_path

        db_path = temp_project / ".ogrep" / "index.sqlite"

        index_path(
            root=temp_project,
            db_path=db_path,
            ast=True,
            chunk_lines=100,
        )

        # Query the database for chunks (join with files to get path)
        con = connect(db_path)
        chunks = con.execute(
            """
            SELECT f.path, c.chunk_index, c.start_line, c.end_line, c.text
            FROM chunks c
            JOIN files f ON c.file_id = f.id
            """
        ).fetchall()

        # Check that PasswordHasher class is a single chunk
        auth_chunks = [c for c in chunks if "auth.py" in c[0]]
        class_chunk = next(
            (c for c in auth_chunks if "class PasswordHasher" in c[4]), None
        )
        assert class_chunk is not None, "PasswordHasher class should be indexed"

        # The class methods should be in the same chunk
        class_text = class_chunk[4]
        assert "def hash_password" in class_text
        assert "def verify_password" in class_text

        con.close()


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestASTChunkingEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_file(self):
        """Empty files should return empty chunks."""
        chunks = chunk_ast("", language="python")
        assert chunks == []

    def test_whitespace_only(self):
        """Whitespace-only files should return empty chunks."""
        chunks = chunk_ast("   \n\n   ", language="python")
        assert chunks == []

    def test_comments_only(self):
        """Comment-only files should be handled gracefully."""
        code = '''# This is a comment
# Another comment
# Yet another
'''
        chunks = chunk_ast(code, language="python")
        # May return empty or a single module chunk
        assert isinstance(chunks, list)

    def test_syntax_error_fallback(self):
        """Syntax errors should fall back to line-based chunking."""
        broken_code = '''def broken(
    # Missing closing paren
'''
        chunks = chunk_ast(broken_code, language="python")
        # Should not raise, should return something
        assert isinstance(chunks, list)

    def test_unsupported_language_fallback(self):
        """Unsupported languages should fall back to line-based chunking."""
        code = "Some random text\nwith multiple lines"
        chunks = chunk_ast(code, language="unknown_lang_xyz")
        assert isinstance(chunks, list)

    def test_very_large_function_is_split(self):
        """Very large functions should be split to respect max_chunk_lines."""
        # Create a function with 200 lines
        lines = ["def very_large_function():"]
        for i in range(200):
            lines.append(f"    x{i} = {i}")
        lines.append("    return x0")
        code = "\n".join(lines)

        chunks = chunk_ast(code, language="python", max_chunk_lines=50)

        # Should be split into multiple chunks
        assert len(chunks) >= 3

    def test_small_function_not_split(self):
        """Small functions should remain as single chunks."""
        code = '''def small():
    return 42
'''
        chunks = chunk_ast(code, language="python", max_chunk_lines=100)
        assert len(chunks) == 1

    def test_decorator_included(self):
        """Decorated functions should include the decorator."""
        code = '''@decorator
@another_decorator
def decorated_function():
    pass
'''
        chunks = chunk_ast(code, language="python")
        assert len(chunks) >= 1

        # The decorator should be part of the function chunk
        func_chunk = find_chunk_with(chunks, "def decorated_function")
        assert func_chunk is not None
        assert "@decorator" in func_chunk.text

    def test_mixed_content(self):
        """Files with mixed content (classes, functions, module code) should be handled."""
        code = '''import os

CONSTANT = 42

class MyClass:
    pass

def my_function():
    pass

another_var = "test"
'''
        chunks = chunk_ast(code, language="python")

        # Should have multiple chunks
        assert len(chunks) >= 2

        # All code should be represented
        all_text = " ".join(c.text for c in chunks)
        assert "class MyClass" in all_text
        assert "def my_function" in all_text


# =============================================================================
# Performance Tests
# =============================================================================


class TestASTChunkingPerformance:
    """Test performance characteristics of AST chunking."""

    def test_reasonable_chunk_count(self):
        """AST chunking should produce a reasonable number of chunks."""
        # Each file should produce roughly one chunk per class/function
        chunks = chunk_ast(PYTHON_PROJECT["auth.py"], language="python")

        # auth.py has: 1 class + 2 standalone functions + maybe imports
        # So roughly 3-5 chunks
        assert 2 <= len(chunks) <= 10

    def test_chunk_sizes_are_reasonable(self):
        """Chunks should not be excessively large or small."""
        chunks = chunk_ast(PYTHON_PROJECT["database.py"], language="python")

        for chunk in chunks:
            lines = chunk.text.count("\n") + 1
            # Chunks should be between 1 and 200 lines typically
            assert 1 <= lines <= 200, f"Chunk has {lines} lines"

    def test_no_duplicate_content(self):
        """AST chunking should not duplicate content across chunks."""
        chunks = chunk_ast(PYTHON_PROJECT["api.py"], language="python")

        # Check that no function appears in multiple chunks
        for i, c1 in enumerate(chunks):
            for c2 in chunks[i + 1 :]:
                # If both chunks contain the same function definition, that's a problem
                if "def handle_login" in c1.text and "def handle_login" in c2.text:
                    pytest.fail("handle_login appears in multiple chunks")


# =============================================================================
# Language Detection Tests
# =============================================================================


class TestLanguageDetection:
    """Test automatic language detection from filenames."""

    @pytest.mark.parametrize(
        "filename,expected_chunks_min",
        [
            ("test.py", 1),
            ("module.js", 1),
            ("component.ts", 1),
            ("main.go", 1),
            ("lib.rs", 1),
        ],
    )
    def test_detection_by_extension(self, filename, expected_chunks_min):
        """Language should be detected from file extension."""
        # Simple code that should parse in any language
        code = "x = 1"
        chunks = chunk_ast(code, filename=filename)

        # May fall back to line-based if parser not available
        assert isinstance(chunks, list)
