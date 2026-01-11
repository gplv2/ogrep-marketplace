"""Pytest fixtures for ogrep tests."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_repo(temp_dir: Path) -> Path:
    """Create a sample repository structure for testing."""
    # Create some sample files
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "main.py").write_text(
        '''"""Main module."""

def hello_world():
    """Print hello world."""
    print("Hello, World!")

def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two numbers."""
    return a + b

if __name__ == "__main__":
    hello_world()
'''
    )

    (temp_dir / "src" / "utils.py").write_text(
        '''"""Utility functions."""

def format_string(s: str) -> str:
    """Format a string by stripping whitespace."""
    return s.strip()

def parse_number(s: str) -> int:
    """Parse a string to integer."""
    return int(s)
'''
    )

    (temp_dir / "README.md").write_text(
        """# Sample Project

This is a sample project for testing ogrep.

## Features

- Feature 1: Hello world
- Feature 2: Calculate sum
- Feature 3: String utilities
"""
    )

    return temp_dir


@pytest.fixture
def db_path(temp_dir: Path) -> Path:
    """Return a path for the test database."""
    return temp_dir / ".ogrep" / "index.sqlite"


@pytest.fixture(autouse=True)
def mock_openai_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Mock OpenAI API for tests that don't need real embeddings.

    Tests that need real embeddings should use @pytest.mark.integration
    and be skipped when OPENAI_API_KEY is not set.
    """
    # Only mock if we're not running integration tests
    if os.environ.get("OGREP_INTEGRATION_TESTS"):
        return

    # Set a fake API key so require_embedding_config() passes
    monkeypatch.setenv("OPENAI_API_KEY", "test-fake-key-for-mocking")

    class MockEmbedding:
        def __init__(self, embedding: list[float]):
            self.embedding = embedding

    class MockResponse:
        def __init__(self, texts: list[str]):
            # Generate deterministic fake embeddings based on text hash
            self.data = []
            for text in texts:
                # Create a simple deterministic embedding from text
                import hashlib

                h = hashlib.sha256(text.encode()).digest()
                # Create 256-dim embedding from hash bytes
                emb = [float(b) / 255.0 for b in h] * 8  # 32 * 8 = 256 dims
                self.data.append(MockEmbedding(emb[:256]))

    class MockEmbeddings:
        def create(self, input: list[str], model: str, **kwargs) -> MockResponse:
            return MockResponse(input)

    class MockOpenAI:
        def __init__(self, **kwargs):
            self.embeddings = MockEmbeddings()

    monkeypatch.setattr("ogrep.embed.OpenAI", MockOpenAI)
