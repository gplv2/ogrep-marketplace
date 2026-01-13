"""Tests for AST-aware chunking."""

from __future__ import annotations

import pytest

from ogrep.chunking import Chunk

# Import will fail if tree-sitter not installed - tests will skip
try:
    from ogrep.ast_chunking import (
        chunk_ast,
        get_language_for_file,
        is_ast_available,
        SUPPORTED_LANGUAGES,
    )

    HAS_TREE_SITTER = is_ast_available()
except ImportError:
    HAS_TREE_SITTER = False

    def chunk_ast(*args, **kwargs):
        return []

    def get_language_for_file(*args):
        return None

    def is_ast_available():
        return False

    SUPPORTED_LANGUAGES = {}


# Skip all tests if tree-sitter not installed
pytestmark = pytest.mark.skipif(
    not HAS_TREE_SITTER, reason="tree-sitter not installed (pip install ogrep[ast])"
)


# =============================================================================
# Python AST Chunking Tests
# =============================================================================


PYTHON_SIMPLE = '''
def hello():
    """Say hello."""
    print("Hello, world!")


def goodbye():
    """Say goodbye."""
    print("Goodbye!")
'''


PYTHON_CLASS = '''
class Calculator:
    """A simple calculator."""

    def __init__(self, value=0):
        self.value = value

    def add(self, x):
        """Add x to the value."""
        self.value += x
        return self.value

    def subtract(self, x):
        """Subtract x from the value."""
        self.value -= x
        return self.value


def standalone_function():
    """A function outside the class."""
    return 42
'''


PYTHON_NESTED = '''
class Outer:
    """Outer class."""

    class Inner:
        """Inner class."""

        def inner_method(self):
            pass

    def outer_method(self):
        def nested_function():
            pass
        return nested_function()
'''


def test_chunk_ast_python_functions():
    """Test that Python functions are chunked as separate units."""
    chunks = chunk_ast(PYTHON_SIMPLE, language="python")

    assert len(chunks) == 2
    assert "def hello" in chunks[0].text
    assert "def goodbye" in chunks[1].text


def test_chunk_ast_python_class_methods():
    """Test that Python class with methods creates semantic chunks."""
    chunks = chunk_ast(PYTHON_CLASS, language="python")

    # Should have: class Calculator (with methods), standalone_function
    # Methods are part of the class chunk, not separate
    assert len(chunks) >= 2

    # Find the class chunk
    class_chunk = next((c for c in chunks if "class Calculator" in c.text), None)
    assert class_chunk is not None
    assert "def add" in class_chunk.text
    assert "def subtract" in class_chunk.text

    # Find standalone function
    func_chunk = next((c for c in chunks if "def standalone_function" in c.text), None)
    assert func_chunk is not None


def test_chunk_ast_preserves_chunk_structure():
    """Test that AST chunks have correct structure."""
    chunks = chunk_ast(PYTHON_SIMPLE, language="python")

    for i, chunk in enumerate(chunks):
        assert isinstance(chunk, Chunk)
        assert chunk.chunk_index == i
        assert chunk.start_line >= 1
        assert chunk.end_line >= chunk.start_line
        assert len(chunk.text) > 0


def test_chunk_ast_line_numbers():
    """Test that line numbers are correct."""
    chunks = chunk_ast(PYTHON_SIMPLE, language="python")

    # First function starts around line 2
    assert chunks[0].start_line <= 3
    # Second function starts later
    assert chunks[1].start_line > chunks[0].end_line


def test_chunk_ast_empty_file():
    """Test chunking an empty file."""
    chunks = chunk_ast("", language="python")
    assert len(chunks) == 0


def test_chunk_ast_no_functions():
    """Test file with only module-level code."""
    code = '''
# Just comments and imports
import os
import sys

x = 1
y = 2
'''
    chunks = chunk_ast(code, language="python")
    # Should still produce at least one chunk with the module-level code
    assert len(chunks) >= 1


def test_chunk_ast_nested_classes():
    """Test that nested classes are handled."""
    chunks = chunk_ast(PYTHON_NESTED, language="python")

    # The outer class should be a single chunk containing everything
    outer_chunk = next((c for c in chunks if "class Outer" in c.text), None)
    assert outer_chunk is not None
    assert "class Inner" in outer_chunk.text


# =============================================================================
# JavaScript AST Chunking Tests
# =============================================================================


JAVASCRIPT_SIMPLE = '''
function greet(name) {
    console.log("Hello, " + name);
}

const farewell = (name) => {
    console.log("Goodbye, " + name);
};

class Person {
    constructor(name) {
        this.name = name;
    }

    sayHello() {
        greet(this.name);
    }
}
'''


@pytest.mark.skipif(
    "javascript" not in SUPPORTED_LANGUAGES,
    reason="JavaScript parser not available",
)
def test_chunk_ast_javascript():
    """Test JavaScript function and class chunking."""
    chunks = chunk_ast(JAVASCRIPT_SIMPLE, language="javascript")

    assert len(chunks) >= 2

    # Should find the function
    func_chunk = next((c for c in chunks if "function greet" in c.text), None)
    assert func_chunk is not None

    # Should find the class
    class_chunk = next((c for c in chunks if "class Person" in c.text), None)
    assert class_chunk is not None


# =============================================================================
# Language Detection Tests
# =============================================================================


@pytest.mark.parametrize(
    "filename,expected_lang",
    [
        ("test.py", "python"),
        ("module.js", "javascript"),
        ("component.ts", "typescript"),
        ("component.tsx", "tsx"),
        ("main.go", "go"),
        ("lib.rs", "rust"),
        ("unknown.xyz", None),
        ("Makefile", None),
        (".gitignore", None),
    ],
)
def test_get_language_for_file(filename, expected_lang):
    """Test language detection from filename."""
    detected = get_language_for_file(filename)

    if expected_lang is None:
        assert detected is None
    else:
        # May be None if that specific parser isn't installed
        assert detected is None or detected == expected_lang


# =============================================================================
# Fallback Behavior Tests
# =============================================================================


def test_chunk_ast_fallback_on_unsupported():
    """Test that unsupported languages fall back to line-based chunking."""
    code = "some random text\nwith multiple lines\nno syntax"

    # Unsupported language should return empty or fall back
    chunks = chunk_ast(code, language="unknown_language")
    # Either empty (no AST) or line-based fallback
    assert isinstance(chunks, list)


def test_chunk_ast_fallback_on_syntax_error():
    """Test that syntax errors don't crash, fall back gracefully."""
    broken_python = '''
def broken_function(
    # Missing closing paren and body
'''
    # Should not raise, should return something reasonable
    chunks = chunk_ast(broken_python, language="python")
    assert isinstance(chunks, list)


# =============================================================================
# Max Chunk Size Tests
# =============================================================================


def test_chunk_ast_respects_max_lines():
    """Test that very large functions are split if they exceed max_lines."""
    # Create a function with many lines
    lines = ["def big_function():"]
    for i in range(200):
        lines.append(f"    x{i} = {i}")
    lines.append("    return x0")
    big_code = "\n".join(lines)

    # With a max of 100 lines, should split
    chunks = chunk_ast(big_code, language="python", max_chunk_lines=100)

    # Should have multiple chunks for this large function
    assert len(chunks) >= 2


def test_chunk_ast_small_functions_not_split():
    """Test that small functions stay together."""
    chunks = chunk_ast(PYTHON_SIMPLE, language="python", max_chunk_lines=100)

    # Each function is small, should be its own chunk
    assert len(chunks) == 2
    assert "def hello" in chunks[0].text
    assert "print(" in chunks[0].text  # Body included


# =============================================================================
# Integration with existing Chunk dataclass
# =============================================================================


def test_chunk_ast_returns_chunk_objects():
    """Test that chunk_ast returns standard Chunk objects."""
    chunks = chunk_ast(PYTHON_SIMPLE, language="python")

    for chunk in chunks:
        assert hasattr(chunk, "chunk_index")
        assert hasattr(chunk, "start_line")
        assert hasattr(chunk, "end_line")
        assert hasattr(chunk, "text")


def test_chunk_ast_with_file_extension():
    """Test chunk_ast with filename for auto-detection."""
    chunks = chunk_ast(PYTHON_SIMPLE, filename="example.py")

    assert len(chunks) >= 2


# =============================================================================
# Availability Check
# =============================================================================


def test_is_ast_available():
    """Test that availability check works."""
    assert is_ast_available() == HAS_TREE_SITTER


def test_supported_languages_is_dict():
    """Test that SUPPORTED_LANGUAGES is a dict."""
    if HAS_TREE_SITTER:
        assert isinstance(SUPPORTED_LANGUAGES, dict)
        assert "python" in SUPPORTED_LANGUAGES
