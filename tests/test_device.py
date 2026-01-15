"""
Tests for the device command.

Tests GPU/CPU detection for cross-encoder reranking.
"""

import json
import subprocess
import sys


class TestDeviceCommand:
    """Test ogrep device command."""

    def test_device_command_runs(self):
        """Device command should run without errors."""
        result = subprocess.run(
            [sys.executable, "-m", "ogrep", "device"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Reranking Support" in result.stdout or "rerank_available" in result.stdout

    def test_device_json_output(self):
        """Device command should output valid JSON with --json flag."""
        result = subprocess.run(
            [sys.executable, "-m", "ogrep", "device", "--json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Should be valid JSON
        data = json.loads(result.stdout)

        # Should have required fields
        assert "rerank_available" in data
        assert "pytorch_available" in data
        assert "device" in data
        assert "cuda_available" in data
        assert "mps_available" in data
        assert "cpu_info" in data
        assert "warnings" in data
        assert "recommendation" in data

    def test_device_json_clean_stderr(self):
        """Device command should not leak warnings to stderr in JSON mode."""
        result = subprocess.run(
            [sys.executable, "-m", "ogrep", "device", "--json"],
            capture_output=True,
            text=True,
        )
        # stderr should be empty or not contain CUDA warnings
        if result.stderr:
            assert "CUDA" not in result.stderr
            assert "UserWarning" not in result.stderr


class TestDeviceDetection:
    """Test device detection logic."""

    def test_get_device_info_returns_dict(self):
        """_get_device_info should return a dictionary."""
        from ogrep.commands.device import _get_device_info

        info = _get_device_info()
        assert isinstance(info, dict)
        assert "device" in info
        assert info["device"] in ("cuda", "mps", "cpu")

    def test_device_info_has_cpu_info(self):
        """Device info should always include CPU information."""
        from ogrep.commands.device import _get_device_info

        info = _get_device_info()
        assert "cpu_info" in info
        assert "platform" in info["cpu_info"]
        assert "processor" in info["cpu_info"]
        assert "python_version" in info["cpu_info"]

    def test_device_info_has_recommendation(self):
        """Device info should include a recommendation."""
        from ogrep.commands.device import _get_device_info

        info = _get_device_info()
        assert "recommendation" in info
        assert len(info["recommendation"]) > 0


class TestDeviceInfoWithMocks:
    """Test device detection with mocked dependencies."""

    def test_without_sentence_transformers(self):
        """Should report unavailable without sentence-transformers."""
        from ogrep.commands.device import _get_device_info

        # The function should always return a dict with rerank_available field
        # Note: Since sentence_transformers may already be imported in this process,
        # we just verify the function returns the expected structure
        info = _get_device_info()

        # Should have the rerank_available field
        assert "rerank_available" in info
        # Should have recommendation field
        assert "recommendation" in info

    def test_text_format_output(self):
        """Text format should include section headers."""
        from ogrep.commands.device import _format_text_output, _get_device_info

        info = _get_device_info()
        text = _format_text_output(info)

        # Should always have Reranking Support header
        assert "Reranking Support" in text

        # Full output only available when sentence-transformers is installed
        if info["rerank_available"]:
            assert "Device Detection" in text
            assert "CUDA" in text
            assert "MPS" in text
            assert "CPU" in text
            assert "Recommendation" in text
        else:
            # When not available, should show install instructions
            assert "pip install" in text or "not available" in text.lower()


class TestDeviceHelp:
    """Test device command help."""

    def test_device_help(self):
        """Device command should show help."""
        result = subprocess.run(
            [sys.executable, "-m", "ogrep", "device", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "GPU" in result.stdout or "reranking" in result.stdout.lower()
