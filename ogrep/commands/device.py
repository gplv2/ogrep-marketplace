"""
Device command for ogrep.

Checks GPU/CPU capabilities for cross-encoder reranking.
This command intentionally loads PyTorch to detect hardware support,
so it's separate from 'health' to avoid unnecessary overhead.

Usage:
    ogrep device           # Human-readable output
    ogrep device --json    # Structured JSON output
"""

from __future__ import annotations

import argparse
import io
import json
import platform
import sys
import warnings
from contextlib import contextmanager
from typing import Any


@contextmanager
def _capture_stderr():
    """Capture stderr to prevent warnings from corrupting output."""
    old_stderr = sys.stderr
    captured = io.StringIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            sys.stderr = captured
            yield captured
        finally:
            sys.stderr = old_stderr


def _get_device_info() -> dict[str, Any]:
    """
    Detect GPU/CPU capabilities for reranking.

    Returns:
        Dictionary with device information including:
        - rerank_available: Whether sentence-transformers is installed
        - pytorch_available: Whether PyTorch is installed
        - device: Best available device (cuda, mps, cpu)
        - cuda_available: CUDA GPU detection
        - mps_available: Apple Silicon MPS detection
        - device_name: Human-readable device name
        - driver_version: GPU driver version if available
        - warnings: Any warnings captured during detection
    """
    info: dict[str, Any] = {
        "rerank_available": False,
        "pytorch_available": False,
        "device": "cpu",
        "cuda_available": False,
        "cuda_version": None,
        "cuda_device_count": 0,
        "cuda_device_name": None,
        "cuda_driver_version": None,
        "mps_available": False,
        "mps_built": False,
        "cpu_info": {
            "platform": platform.system(),
            "processor": platform.processor() or platform.machine(),
            "python_version": platform.python_version(),
        },
        "warnings": [],
        "recommendation": "",
    }

    # Check if sentence-transformers is available
    try:
        import sentence_transformers  # noqa: F401

        info["rerank_available"] = True
        info["sentence_transformers_version"] = getattr(
            sentence_transformers, "__version__", "unknown"
        )
    except ImportError:
        info["recommendation"] = (
            "Reranking not available. Install with: pip install 'ogrep[rerank]'"
        )
        return info

    # Check PyTorch availability (comes with sentence-transformers)
    captured_warnings: list[str] = []

    with _capture_stderr() as captured:
        try:
            import torch

            info["pytorch_available"] = True
            info["pytorch_version"] = torch.__version__

            # Check CUDA
            try:
                info["cuda_available"] = torch.cuda.is_available()
                if info["cuda_available"]:
                    info["cuda_version"] = torch.version.cuda
                    info["cuda_device_count"] = torch.cuda.device_count()
                    if info["cuda_device_count"] > 0:
                        info["cuda_device_name"] = torch.cuda.get_device_name(0)
                        # Try to get driver version
                        try:
                            info["cuda_driver_version"] = (
                                torch.cuda.get_device_properties(0).major,
                                torch.cuda.get_device_properties(0).minor,
                            )
                        except Exception:
                            pass
                    info["device"] = "cuda"
            except Exception as e:
                captured_warnings.append(f"CUDA detection error: {e}")

            # Check MPS (Apple Silicon)
            try:
                info["mps_built"] = torch.backends.mps.is_built()
                info["mps_available"] = (
                    torch.backends.mps.is_available() if info["mps_built"] else False
                )
                if info["mps_available"] and info["device"] == "cpu":
                    info["device"] = "mps"
            except Exception:
                # MPS not available on this platform
                pass

        except ImportError as e:
            info["warnings"].append(f"PyTorch import failed: {e}")
            return info

    # Parse any stderr warnings (CUDA driver issues, etc.)
    stderr_text = captured.getvalue().strip()
    if stderr_text:
        for line in stderr_text.split("\n"):
            line = line.strip()
            if line and "UserWarning:" in line:
                idx = line.find("UserWarning:")
                msg = line[idx + len("UserWarning:") :].strip()
                if msg:
                    captured_warnings.append(msg)
            elif "warning" in line.lower() and line:
                captured_warnings.append(line)

    info["warnings"] = captured_warnings

    # Generate recommendation
    if info["device"] == "cuda":
        info["recommendation"] = (
            f"CUDA GPU available ({info['cuda_device_name']}). "
            "Reranking will use GPU acceleration (~10x faster)."
        )
    elif info["device"] == "mps":
        info["recommendation"] = (
            "Apple Silicon MPS available. Reranking will use GPU acceleration (~3-5x faster)."
        )
    else:
        if captured_warnings:
            info["recommendation"] = (
                "CPU-only mode (GPU detection had warnings). "
                "Reranking will work but may be slower. "
                "Consider using --rerank-top 20-30 for faster response."
            )
        else:
            info["recommendation"] = (
                "CPU-only mode (no GPU detected). "
                "Reranking will work but may be slower. "
                "Consider using --rerank-top 20-30 for faster response."
            )

    return info


def _format_text_output(info: dict[str, Any]) -> str:
    """Format device info as human-readable text."""
    lines = []

    lines.append("── Reranking Support ──")
    if info["rerank_available"]:
        lines.append(
            f"  sentence-transformers: {info.get('sentence_transformers_version', 'installed')}"
        )
    else:
        lines.append("  sentence-transformers: NOT INSTALLED")
        lines.append("")
        lines.append(info["recommendation"])
        return "\n".join(lines)

    if info["pytorch_available"]:
        lines.append(f"  PyTorch: {info.get('pytorch_version', 'installed')}")
    else:
        lines.append("  PyTorch: NOT INSTALLED")

    lines.append("")
    lines.append("── Device Detection ──")
    lines.append(f"  Selected device: {info['device'].upper()}")

    # CUDA info
    lines.append("")
    lines.append("── CUDA (NVIDIA GPU) ──")
    if info["cuda_available"]:
        lines.append("  Available: Yes")
        lines.append(f"  CUDA version: {info.get('cuda_version', 'unknown')}")
        lines.append(f"  Device count: {info['cuda_device_count']}")
        if info["cuda_device_name"]:
            lines.append(f"  GPU: {info['cuda_device_name']}")
    else:
        lines.append("  Available: No")

    # MPS info
    lines.append("")
    lines.append("── MPS (Apple Silicon) ──")
    if info["mps_available"]:
        lines.append("  Available: Yes")
    elif info["mps_built"]:
        lines.append("  Built: Yes (but not available)")
    else:
        lines.append("  Available: No (not on macOS or unsupported)")

    # CPU info
    lines.append("")
    lines.append("── CPU ──")
    cpu = info.get("cpu_info", {})
    lines.append(f"  Platform: {cpu.get('platform', 'unknown')}")
    lines.append(f"  Processor: {cpu.get('processor', 'unknown')}")
    lines.append(f"  Python: {cpu.get('python_version', 'unknown')}")

    # Warnings
    if info["warnings"]:
        lines.append("")
        lines.append("── Warnings ──")
        for warning in info["warnings"]:
            # Truncate long warnings for readability
            if len(warning) > 100:
                warning = warning[:97] + "..."
            lines.append(f"  ! {warning}")

    # Recommendation
    lines.append("")
    lines.append("── Recommendation ──")
    lines.append(f"  {info['recommendation']}")

    return "\n".join(lines)


def cmd_device(args: argparse.Namespace) -> int:
    """
    Check GPU/CPU capabilities for reranking.

    Detects available hardware acceleration (CUDA, MPS) and provides
    recommendations for optimal reranking performance.

    Args:
        args: Parsed command-line arguments containing:
            - json: Whether to output as JSON

    Returns:
        Exit code (0 for success).
    """
    use_json = getattr(args, "json", False)

    info = _get_device_info()

    if use_json:
        print(json.dumps(info, indent=2))
    else:
        print(_format_text_output(info))

    return 0
