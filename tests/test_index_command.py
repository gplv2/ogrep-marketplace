"""Tests for ogrep.commands.index module helpers."""

from __future__ import annotations

from pathlib import Path

from ogrep.commands.index import (
    _accumulate_stat,
    _extract_mime_category,
    _format_size,
    _safe_relative_path,
    _should_review,
)


class TestFormatSize:
    """Tests for _format_size helper (already exists)."""

    def test_bytes(self) -> None:
        assert _format_size(0) == "0B"
        assert _format_size(512) == "512B"
        assert _format_size(1023) == "1023B"

    def test_kilobytes(self) -> None:
        assert _format_size(1024) == "1.0KB"
        assert _format_size(2048) == "2.0KB"
        assert _format_size(10240) == "10.0KB"

    def test_megabytes(self) -> None:
        assert _format_size(1024 * 1024) == "1.0MB"
        assert _format_size(5 * 1024 * 1024) == "5.0MB"


class TestSafeRelativePath:
    """Tests for _safe_relative_path helper."""

    def test_relative_path_within_root(self, tmp_path: Path) -> None:
        """Path within root returns relative path."""
        file_path = tmp_path / "src" / "main.py"
        result = _safe_relative_path(file_path, tmp_path)
        assert result == Path("src/main.py")

    def test_path_outside_root_returns_absolute(self) -> None:
        """Path outside root returns the original path."""
        file_path = Path("/other/location/file.py")
        root = Path("/home/user/project")
        result = _safe_relative_path(file_path, root)
        assert result == file_path

    def test_same_as_root_returns_dot(self, tmp_path: Path) -> None:
        """Path equal to root returns empty relative path."""
        result = _safe_relative_path(tmp_path, tmp_path)
        assert result == Path(".")


class TestAccumulateStat:
    """Tests for _accumulate_stat helper."""

    def test_accumulates_new_key(self) -> None:
        """Adds new key with count=1 and size."""
        stats: dict[str, tuple[int, int]] = {}
        _accumulate_stat(stats, ".py", 1000)
        assert stats[".py"] == (1, 1000)

    def test_accumulates_existing_key(self) -> None:
        """Increments count and adds to size for existing key."""
        stats: dict[str, tuple[int, int]] = {".py": (2, 5000)}
        _accumulate_stat(stats, ".py", 1500)
        assert stats[".py"] == (3, 6500)

    def test_multiple_keys(self) -> None:
        """Handles multiple keys independently."""
        stats: dict[str, tuple[int, int]] = {}
        _accumulate_stat(stats, ".py", 100)
        _accumulate_stat(stats, ".ts", 200)
        _accumulate_stat(stats, ".py", 50)
        assert stats[".py"] == (2, 150)
        assert stats[".ts"] == (1, 200)


class TestExtractMimeCategory:
    """Tests for _extract_mime_category helper."""

    def test_extracts_category_from_full_mime(self) -> None:
        assert _extract_mime_category("text/x-python") == "text"
        assert _extract_mime_category("application/json") == "application"
        assert _extract_mime_category("image/png") == "image"

    def test_handles_complex_mime_types(self) -> None:
        assert _extract_mime_category("text/x-script.python") == "text"
        assert _extract_mime_category("application/x-sqlite3") == "application"

    def test_handles_none(self) -> None:
        assert _extract_mime_category(None) == "text"

    def test_handles_empty_string(self) -> None:
        assert _extract_mime_category("") == "text"

    def test_handles_no_slash(self) -> None:
        assert _extract_mime_category("unknown") == "unknown"


class TestShouldReview:
    """Tests for _should_review helper (already exists)."""

    def test_review_extensions(self, tmp_path: Path) -> None:
        """Files with review extensions are flagged."""
        assert _should_review(tmp_path / "debug.log", 100) is not None
        assert _should_review(tmp_path / "data.sql", 100) is not None
        assert _should_review(tmp_path / "backup.bak", 100) is not None

    def test_normal_code_files(self, tmp_path: Path) -> None:
        """Normal code files are not flagged."""
        assert _should_review(tmp_path / "main.py", 100) is None
        assert _should_review(tmp_path / "app.ts", 100) is None

    def test_large_files_without_code_extension(self, tmp_path: Path) -> None:
        """Large files without code extensions are flagged."""
        large_size = 600 * 1024  # 600KB
        assert _should_review(tmp_path / "data.txt", large_size) is not None
        assert _should_review(tmp_path / "readme", large_size) is not None

    def test_large_code_files_not_flagged(self, tmp_path: Path) -> None:
        """Large code files are not flagged."""
        large_size = 600 * 1024  # 600KB
        assert _should_review(tmp_path / "big_module.py", large_size) is None
