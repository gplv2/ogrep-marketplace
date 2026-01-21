---
name: device
description: Detect hardware acceleration support (CUDA, MPS) for cross-encoder reranking
allowed-tools: Bash
---

# ogrep device

Detect GPU/CPU capabilities for cross-encoder reranking. Useful for understanding performance expectations and troubleshooting.

## Usage

```bash
# Check hardware (JSON output is default)
ogrep device

# Human-readable output
ogrep device --no-json
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | yes | Output as JSON (default for AI/machine use) |
| `--no-json` | - | Output as human-readable text |

## JSON Output

```json
{
  "device": "cuda",
  "device_name": "NVIDIA GeForce RTX 3080",
  "cuda_available": true,
  "mps_available": false,
  "recommendation": "GPU acceleration available. Reranking will be fast."
}
```

Or on CPU-only:

```json
{
  "device": "cpu",
  "device_name": null,
  "cuda_available": false,
  "mps_available": false,
  "recommendation": "No GPU detected. Reranking will work but be slower. Consider --rerank-top 20 for faster results."
}
```

## Hardware Performance

| Hardware | Reranking Speed | Notes |
|----------|-----------------|-------|
| **NVIDIA GPU (CUDA)** | ~10x faster | Requires CUDA 12.x drivers |
| **Apple Silicon (MPS)** | ~3-5x faster | Automatic on macOS 12.3+ |
| **CPU only** | Baseline | Works but slower (2-5 seconds per query) |

## When to Use

- **Before using `--rerank`** - understand what performance to expect
- **Troubleshooting slow queries** - check if GPU is being detected
- **Setting up a new machine** - verify CUDA/MPS is working

## Notes

- This command loads PyTorch to detect GPU capabilities
- If no GPU is detected, reranking still works (just slower)
- Use `--rerank-top 20` on CPU for faster results
- ogrep gracefully falls back to CPU if GPU detection fails
