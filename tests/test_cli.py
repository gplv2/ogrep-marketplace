"""CLI smoke tests."""

from __future__ import annotations

import subprocess
import sys


def test_cli_help() -> None:
    """Test that ogrep --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "semantic grep" in result.stdout.lower()


def test_cli_version() -> None:
    """Test that ogrep --version works."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.7.1" in result.stdout


def test_cli_index_help() -> None:
    """Test that ogrep index --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "index", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--db" in result.stdout
    assert "--profile" in result.stdout


def test_cli_query_help() -> None:
    """Test that ogrep query --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "query", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--top" in result.stdout


def test_cli_reset_help() -> None:
    """Test that ogrep reset --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "reset", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--force" in result.stdout


def test_cli_reindex_help() -> None:
    """Test that ogrep reindex --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "reindex", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_clean_help() -> None:
    """Test that ogrep clean --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "clean", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--vacuum" in result.stdout


def test_cli_status_help() -> None:
    """Test that ogrep status --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "status", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_models() -> None:
    """Test that ogrep models works."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "models"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "text-embedding-3-small" in result.stdout
    assert "text-embedding-3-large" in result.stdout
    assert "OGREP_MODEL" in result.stdout


def test_cli_model_flag_in_help() -> None:
    """Test that -m flag is documented in help."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "index", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "-m" in result.stdout or "--model" in result.stdout
    assert "small" in result.stdout.lower() or "large" in result.stdout.lower()


def test_cli_health_help() -> None:
    """Test that ogrep health --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "ogrep", "health", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--vacuum" in result.stdout
    assert "--rebuild-fts" in result.stdout
    assert "--integrity" in result.stdout
    assert "--full" in result.stdout
