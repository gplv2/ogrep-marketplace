"""Tests for file type detection module."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ogrep.filetype import (
    FileTypeResult,
    _is_text_mime,
    _null_byte_check,
    detect_file_types_batch,
    has_file_command,
)


class TestMimeTypeClassification:
    """Test MIME type classification logic."""

    def test_text_plain_is_text(self) -> None:
        assert _is_text_mime("text/plain") is True

    def test_text_python_is_text(self) -> None:
        assert _is_text_mime("text/x-python") is True

    def test_text_c_is_text(self) -> None:
        assert _is_text_mime("text/x-c") is True

    def test_application_javascript_is_text(self) -> None:
        assert _is_text_mime("application/javascript") is True

    def test_application_json_is_text(self) -> None:
        assert _is_text_mime("application/json") is True

    def test_application_xml_is_text(self) -> None:
        assert _is_text_mime("application/xml") is True

    def test_application_shell_is_text(self) -> None:
        assert _is_text_mime("application/x-sh") is True
        assert _is_text_mime("application/x-shellscript") is True

    def test_empty_file_is_text(self) -> None:
        assert _is_text_mime("application/x-empty") is True
        assert _is_text_mime("inode/x-empty") is True

    def test_sqlite_is_not_text(self) -> None:
        assert _is_text_mime("application/x-sqlite3") is False

    def test_executable_is_not_text(self) -> None:
        assert _is_text_mime("application/x-executable") is False

    def test_octet_stream_is_not_text(self) -> None:
        assert _is_text_mime("application/octet-stream") is False

    def test_image_is_not_text(self) -> None:
        assert _is_text_mime("image/png") is False
        assert _is_text_mime("image/jpeg") is False

    def test_audio_is_not_text(self) -> None:
        assert _is_text_mime("audio/mpeg") is False

    def test_video_is_not_text(self) -> None:
        assert _is_text_mime("video/mp4") is False

    def test_unknown_type_is_not_text(self) -> None:
        """Unknown types default to not text for safety."""
        assert _is_text_mime("application/x-unknown-type") is False


class TestNullByteCheck:
    """Test null-byte heuristic."""

    def test_text_has_no_null(self) -> None:
        assert _null_byte_check(b"Hello world\n") is True

    def test_binary_has_null(self) -> None:
        assert _null_byte_check(b"\x00\x01\x02") is False

    def test_utf8_bom_is_text(self) -> None:
        assert _null_byte_check(b"\xef\xbb\xbfHello") is True

    def test_empty_is_text(self) -> None:
        assert _null_byte_check(b"") is True


class TestBatchDetection:
    """Test batch file detection."""

    def test_detect_python_files(self, temp_dir: Path) -> None:
        """Python files should be detected as text."""
        py_file = temp_dir / "test.py"
        py_file.write_text("print('hello')")

        results = detect_file_types_batch([py_file])

        assert py_file in results
        assert results[py_file].is_text is True

    def test_detect_empty_file(self, temp_dir: Path) -> None:
        """Empty files should be detected as text."""
        empty_file = temp_dir / "empty.py"
        empty_file.write_text("")

        results = detect_file_types_batch([empty_file])

        assert empty_file in results
        assert results[empty_file].is_text is True

    @pytest.mark.skipif(not has_file_command(), reason="file command not available")
    def test_detect_sqlite_database(self, temp_dir: Path) -> None:
        """SQLite databases should not be detected as text."""
        db_file = temp_dir / "test.db"
        conn = sqlite3.connect(db_file)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        results = detect_file_types_batch([db_file])

        assert db_file in results
        assert results[db_file].is_text is False
        assert "sqlite" in (results[db_file].mime_type or "").lower()

    @pytest.mark.skipif(not has_file_command(), reason="file command not available")
    def test_detect_extensionless_binary(self, temp_dir: Path) -> None:
        """Binary file without extension should not be text."""
        bin_file = temp_dir / "data"
        # SQLite header
        bin_file.write_bytes(b"SQLite format 3\x00")

        results = detect_file_types_batch([bin_file])

        assert bin_file in results
        assert results[bin_file].is_text is False

    def test_batch_mixed_files(self, temp_dir: Path) -> None:
        """Batch should handle mixed text and binary files."""
        text_file = temp_dir / "readme.py"
        text_file.write_text("# Hello world")

        binary_file = temp_dir / "image"
        # PNG header
        binary_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")

        results = detect_file_types_batch([text_file, binary_file])

        assert results[text_file].is_text is True
        assert results[binary_file].is_text is False

    def test_empty_batch(self) -> None:
        """Empty batch should return empty dict."""
        results = detect_file_types_batch([])
        assert results == {}


class TestFileTypeResult:
    """Test FileTypeResult dataclass."""

    def test_result_is_frozen(self, temp_dir: Path) -> None:
        """FileTypeResult should be immutable."""
        result = FileTypeResult(
            path=temp_dir / "test.py",
            mime_type="text/plain",
            is_text=True,
            detection_method="file_cmd",
        )
        with pytest.raises(AttributeError):  # Cannot modify frozen dataclass
            result.is_text = False  # type: ignore


class TestFileCommandFallback:
    """Test fallback behavior when file command unavailable."""

    def test_fallback_to_null_byte(self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should fall back to null-byte check."""
        monkeypatch.setattr("ogrep.filetype._FILE_CMD", None)

        text_file = temp_dir / "test.py"
        text_file.write_text("# Python code")

        results = detect_file_types_batch([text_file])

        assert results[text_file].is_text is True
        assert results[text_file].detection_method == "null_byte"
        assert results[text_file].mime_type is None

    def test_fallback_detects_binary(self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Null-byte fallback should detect binary files."""
        monkeypatch.setattr("ogrep.filetype._FILE_CMD", None)

        binary_file = temp_dir / "data"
        binary_file.write_bytes(b"\x00\x01\x02\x03")

        results = detect_file_types_batch([binary_file])

        assert results[binary_file].is_text is False
        assert results[binary_file].detection_method == "null_byte"
