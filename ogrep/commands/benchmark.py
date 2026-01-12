"""
Benchmark command for ogrep.

Comprehensive embedding model comparison with accuracy, speed, and
configuration recommendations across chunk sizes and overlap values.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..indexer import index_path, iter_files
from ..models import MODEL_ALIASES, MODELS, get_model, resolve_model
from ..search import query as search_query

# Reuse patterns from tune.py
SIGNIFICANT_PATTERNS = [
    # Python
    (r"^\s*def\s+(\w+)\s*\(", "function {0}"),
    (r"^\s*class\s+(\w+)", "class {0}"),
    (r"^\s*async\s+def\s+(\w+)", "async function {0}"),
    # JavaScript/TypeScript
    (r"^\s*function\s+(\w+)\s*\(", "function {0}"),
    (r"^\s*(?:export\s+)?class\s+(\w+)", "class {0}"),
    (r"^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(", "function {0}"),
    # Go
    (r"^\s*func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(", "function {0}"),
    (r"^\s*type\s+(\w+)\s+struct", "struct {0}"),
    # Rust
    (r"^\s*(?:pub\s+)?fn\s+(\w+)", "function {0}"),
    (r"^\s*(?:pub\s+)?struct\s+(\w+)", "struct {0}"),
    # Java/Kotlin
    (r"^\s*(?:public|private|protected)?\s*class\s+(\w+)", "class {0}"),
    # Ruby
    (r"^\s*def\s+(\w+)", "method {0}"),
    (r"^\s*class\s+(\w+)", "class {0}"),
]


@dataclass(frozen=True)
class BenchmarkResult:
    """Single benchmark test result."""

    model: str
    dimensions: int
    chunk_size: int
    overlap: int
    accuracy: float
    hits: int
    total_samples: int
    embed_time_s: float
    query_time_s: float
    index_time_s: float


@dataclass
class ModelReport:
    """Aggregated results for one model."""

    model: str
    model_alias: str
    dimensions: int
    best_chunk_size: int
    best_overlap: int
    best_accuracy: float
    avg_embed_time: float
    avg_query_time: float
    avg_index_time: float
    all_results: list[BenchmarkResult] = field(default_factory=list)


def _get_model_alias(model_id: str) -> str:
    """Get shortest alias for a model ID."""
    for alias, mid in MODEL_ALIASES.items():
        if mid == model_id and len(alias) < len(model_id):
            return alias
    return model_id


def _detect_available_models() -> dict[str, bool]:
    """
    Auto-detect which embedding models are accessible.

    Returns:
        Dict mapping model ID to availability status.
    """
    available: dict[str, bool] = {}

    # Check OpenAI models
    if os.environ.get("OPENAI_API_KEY"):
        available["text-embedding-3-small"] = True
        available["text-embedding-3-large"] = True

    # Check local models via OGREP_BASE_URL
    base_url = os.environ.get("OGREP_BASE_URL")
    if base_url:
        # Assume standard local models are available
        # LM Studio JIT loads them on demand
        for model_id in MODELS:
            if MODELS[model_id].price_per_million == 0.0:
                available[model_id] = True

    return available


def _extract_significant_lines(
    root: Path,
    max_samples: int = 10,
) -> list[tuple[Path, int, str, str]]:
    """
    Extract significant code lines from source files.

    Returns:
        List of (file_path, line_number, original_line, semantic_query) tuples.
    """
    candidates: list[tuple[Path, int, str, str]] = []

    for file_path in iter_files(root):
        if not file_path.is_file():
            continue

        try:
            content = file_path.read_text(errors="ignore")
        except Exception:
            continue

        for line_num, line in enumerate(content.splitlines(), start=1):
            for pattern, query_template in SIGNIFICANT_PATTERNS:
                match = re.match(pattern, line)
                if match:
                    name = match.group(1)
                    # Skip dunder methods and test functions
                    if name.startswith("__") or name.startswith("test_"):
                        continue
                    query = f"where is the {query_template.format(name)} defined"
                    candidates.append((file_path, line_num, line.strip(), query))
                    break

    if len(candidates) > max_samples:
        candidates = random.sample(candidates, max_samples)

    return candidates


def _test_configuration(
    root: Path,
    db_path: Path,
    model: str,
    chunk_size: int,
    overlap: int,
    samples: list[tuple[Path, int, str, str]],
) -> BenchmarkResult:
    """
    Test one model/chunk/overlap configuration.

    Returns:
        BenchmarkResult with accuracy and timing metrics.
    """
    # Index with timing
    index_start = time.perf_counter()
    index_path(
        root=root,
        db_path=db_path,
        model=model,
        chunk_lines=chunk_size,
        overlap=overlap,
    )
    index_time = time.perf_counter() - index_start

    # Query with timing
    hits = 0
    total_score = 0.0
    query_time = 0.0

    for file_path, line_num, _original, query in samples:
        query_start = time.perf_counter()
        results = search_query(db_path=db_path, q=query, top_k=5, model=model)
        query_time += time.perf_counter() - query_start

        file_str = str(file_path.resolve())
        for i, hit in enumerate(results):
            if hit.path == file_str:
                if hit.start_line <= line_num <= hit.end_line:
                    hits += 1
                    total_score += (5 - i) / 5
                    break

    accuracy = total_score / len(samples) if samples else 0.0
    dimensions = get_model(model).dimensions

    # Estimate embed time from index time (rough, as it includes DB writes)
    embed_time = index_time * 0.8  # ~80% is embedding

    return BenchmarkResult(
        model=model,
        dimensions=dimensions,
        chunk_size=chunk_size,
        overlap=overlap,
        accuracy=accuracy,
        hits=hits,
        total_samples=len(samples),
        embed_time_s=embed_time,
        query_time_s=query_time,
        index_time_s=index_time,
    )


def _format_results_table(reports: list[ModelReport], verbose: bool = False) -> str:
    """Format benchmark results as ASCII table."""
    lines: list[str] = []

    # Header
    lines.append("RESULTS BY MODEL")
    lines.append("-" * 80)
    lines.append(
        f"{'Model':<25} {'Dims':>5} {'Chunk/Overlap':>14} {'Accuracy':>9} {'Index':>8} {'Query':>8}"
    )
    lines.append("-" * 80)

    # Find best accuracy
    best_accuracy = max(r.best_accuracy for r in reports) if reports else 0

    for report in sorted(reports, key=lambda r: -r.best_accuracy):
        marker = " *" if report.best_accuracy == best_accuracy else ""
        lines.append(
            f"{report.model_alias:<25} {report.dimensions:>5} "
            f"{report.best_chunk_size:>6} / {report.best_overlap:<5} "
            f"{report.best_accuracy:>8.2f} {report.avg_index_time:>7.2f}s "
            f"{report.avg_query_time:>7.3f}s{marker}"
        )

    lines.append("-" * 80)

    # Detailed breakdown for best model
    if verbose and reports:
        best_report = max(reports, key=lambda r: r.best_accuracy)
        lines.append("")
        lines.append(f"DETAILED BREAKDOWN: {best_report.model_alias}")
        lines.append("-" * 60)
        lines.append(f"{'Chunk':>6} {'Overlap':>8} {'Accuracy':>10} {'Hits':>8}")
        lines.append("-" * 60)

        for result in sorted(best_report.all_results, key=lambda r: -r.accuracy):
            marker = " *" if result.accuracy == best_report.best_accuracy else ""
            lines.append(
                f"{result.chunk_size:>6} {result.overlap:>8} "
                f"{result.accuracy:>10.2f} "
                f"{result.hits:>3}/{result.total_samples}{marker}"
            )

        lines.append("-" * 60)

    return "\n".join(lines)


def _generate_recommendations(reports: list[ModelReport]) -> str:
    """Generate recommendation text based on results."""
    lines: list[str] = []
    lines.append("RECOMMENDATIONS")
    lines.append("=" * 80)
    lines.append("")

    if not reports:
        lines.append("No models tested.")
        return "\n".join(lines)

    # Best overall
    best = max(reports, key=lambda r: r.best_accuracy)
    model_info = get_model(best.model)
    cost = (
        "FREE"
        if model_info.price_per_million == 0
        else f"${model_info.price_per_million:.2f}/M tokens"
    )

    lines.append(f"* BEST OVERALL: {best.model_alias}")
    lines.append(
        f"  Accuracy: {best.best_accuracy:.0%} | Speed: {best.avg_index_time:.2f}s | Cost: {cost}"
    )
    lines.append(f"  Optimal: {best.best_chunk_size}-line chunks, {best.best_overlap}-line overlap")
    lines.append("")

    # Best cloud (if different)
    cloud_reports = [r for r in reports if get_model(r.model).price_per_million > 0]
    if cloud_reports:
        best_cloud = max(cloud_reports, key=lambda r: r.best_accuracy)
        if best_cloud.model != best.model:
            cloud_info = get_model(best_cloud.model)
            lines.append(f"* BEST CLOUD: {best_cloud.model_alias}")
            lines.append(
                f"  Accuracy: {best_cloud.best_accuracy:.0%} | "
                f"Cost: ${cloud_info.price_per_million:.2f}/M tokens"
            )
            lines.append(
                f"  Optimal: {best_cloud.best_chunk_size}-line chunks, "
                f"{best_cloud.best_overlap}-line overlap"
            )
            lines.append("")

    # Best local (if different)
    local_reports = [r for r in reports if get_model(r.model).price_per_million == 0]
    if local_reports:
        best_local = max(local_reports, key=lambda r: r.best_accuracy)
        if best_local.model != best.model:
            lines.append(f"* BEST LOCAL: {best_local.model_alias}")
            lines.append(
                f"  Accuracy: {best_local.best_accuracy:.0%} | "
                f"Speed: {best_local.avg_index_time:.2f}s | Cost: FREE"
            )
            lines.append("")

    # Quick setup
    lines.append(f"QUICK SETUP ({best.model_alias}):")
    if get_model(best.model).price_per_million == 0:
        lines.append("  export OGREP_BASE_URL=http://localhost:1234/v1")
    lines.append(f"  export OGREP_MODEL={best.model_alias}")
    lines.append(f"  export OGREP_CHUNK_LINES={best.best_chunk_size}")
    lines.append("  ogrep reindex .")

    return "\n".join(lines)


def cmd_benchmark(args: argparse.Namespace) -> int:
    """
    Run comprehensive embedding model benchmark.

    Compares all available models across chunk sizes and overlaps,
    measuring accuracy, speed, and generating recommendations.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success).
    """
    root = Path(args.path).resolve()

    # Parse chunk sizes and overlaps
    chunk_sizes = [int(x) for x in args.chunks.split(",")]
    overlaps = [int(x) for x in args.overlaps.split(",")]

    # Header
    print("=" * 80)
    print("OGREP MODEL BENCHMARK")
    print("=" * 80)
    print(
        f"Testing {args.samples} code patterns | Chunks: {args.chunks} | Overlaps: {args.overlaps}"
    )
    print()

    # Detect available models
    available = _detect_available_models()

    # Filter by flags
    if args.local_only:
        available = {k: v for k, v in available.items() if get_model(k).price_per_million == 0}
    elif args.cloud_only:
        available = {k: v for k, v in available.items() if get_model(k).price_per_million > 0}

    # Override with explicit models
    if args.models:
        explicit = {}
        for m in args.models:
            resolved = resolve_model(m)
            explicit[resolved] = True
        available = explicit

    if not available:
        print("No models available for testing.")
        print("Set OPENAI_API_KEY for cloud models or OGREP_BASE_URL for local models.")
        return 1

    print("Detected models:")
    for model_id in sorted(available.keys()):
        model_info = get_model(model_id)
        model_type = "cloud" if model_info.price_per_million > 0 else "local"
        alias = _get_model_alias(model_id)
        print(f"  + {alias} ({model_type})")
    print()

    # Extract test samples
    print("Analyzing codebase for significant patterns...")
    samples = _extract_significant_lines(root, max_samples=args.samples)

    if len(samples) < 3:
        print("Not enough significant code patterns found for benchmarking.")
        print("Need at least 3 function/class definitions.")
        return 1

    print(f"Found {len(samples)} test patterns")
    print()

    # Run benchmarks
    reports: list[ModelReport] = []

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            for model_id in sorted(available.keys()):
                alias = _get_model_alias(model_id)
                print(f"Testing {alias}...")

                model_results: list[BenchmarkResult] = []

                for chunk_size in chunk_sizes:
                    for overlap in overlaps:
                        if overlap >= chunk_size:
                            continue  # Skip invalid overlap

                        db_path = Path(tmpdir) / f"{model_id}_{chunk_size}_{overlap}.sqlite"

                        try:
                            result = _test_configuration(
                                root=root,
                                db_path=db_path,
                                model=model_id,
                                chunk_size=chunk_size,
                                overlap=overlap,
                                samples=samples,
                            )
                            model_results.append(result)

                            if args.verbose:
                                print(
                                    f"  chunk={chunk_size} overlap={overlap}: "
                                    f"accuracy={result.accuracy:.2f} ({result.hits}/{result.total_samples})"
                                )
                        except Exception as e:
                            if args.verbose:
                                print(f"  chunk={chunk_size} overlap={overlap}: failed - {e}")

                if model_results:
                    best = max(model_results, key=lambda r: r.accuracy)
                    avg_index = sum(r.index_time_s for r in model_results) / len(model_results)
                    avg_query = sum(r.query_time_s for r in model_results) / len(model_results)
                    avg_embed = sum(r.embed_time_s for r in model_results) / len(model_results)

                    report = ModelReport(
                        model=model_id,
                        model_alias=alias,
                        dimensions=get_model(model_id).dimensions,
                        best_chunk_size=best.chunk_size,
                        best_overlap=best.overlap,
                        best_accuracy=best.accuracy,
                        avg_embed_time=avg_embed,
                        avg_query_time=avg_query,
                        avg_index_time=avg_index,
                        all_results=model_results,
                    )
                    reports.append(report)

                    print(
                        f"  Best: accuracy={best.accuracy:.2f} at chunk={best.chunk_size}/overlap={best.overlap}"
                    )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl-C).")
        print("Benchmark cancelled. No results saved.")
        return 130  # Standard SIGINT exit code (128 + 2)

    print()

    # Output results
    if args.json:
        # JSON output
        output = {
            "models": [
                {
                    "model": r.model,
                    "alias": r.model_alias,
                    "dimensions": r.dimensions,
                    "best_chunk_size": r.best_chunk_size,
                    "best_overlap": r.best_overlap,
                    "best_accuracy": r.best_accuracy,
                    "avg_index_time_s": r.avg_index_time,
                    "avg_query_time_s": r.avg_query_time,
                    "results": [
                        {
                            "chunk_size": res.chunk_size,
                            "overlap": res.overlap,
                            "accuracy": res.accuracy,
                            "hits": res.hits,
                            "total_samples": res.total_samples,
                            "index_time_s": res.index_time_s,
                            "query_time_s": res.query_time_s,
                        }
                        for res in r.all_results
                    ],
                }
                for r in reports
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        # Table output
        print(_format_results_table(reports, verbose=args.verbose))
        print()
        print(_generate_recommendations(reports))

    # Save optimal settings
    if args.save and reports:
        best = max(reports, key=lambda r: r.best_accuracy)
        env_file = root / ".env"

        env_vars = {
            "OGREP_MODEL": best.model_alias,
            "OGREP_CHUNK_LINES": str(best.best_chunk_size),
        }

        if env_file.exists():
            content = env_file.read_text()
            lines = content.splitlines()
        else:
            lines = []

        for var, value in env_vars.items():
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{var}="):
                    lines[i] = f"{var}={value}"
                    found = True
                    break
            if not found:
                lines.append(f"{var}={value}")

        env_file.write_text("\n".join(lines) + "\n")
        print(f"\nSaved optimal settings to {env_file}")

    return 0
