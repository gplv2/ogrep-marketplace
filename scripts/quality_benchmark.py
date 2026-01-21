#!/usr/bin/env python3
"""
Reranking Quality Benchmark

Compares reranking models on accuracy using ground truth queries.
Calculates Hit@1, Hit@3, Hit@5, and MRR metrics.
"""

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Ground truth: 10 queries with expected top file
GROUND_TRUTH = [
    # Existing queries (from ground-truth-queries-julan-peppol.md)
    {
        "id": 1,
        "query": "where are legacy invoices imported",
        "expected": "backend/src/ledger/legacy.py",
        "category": "Import/export",
    },
    {
        "id": 2,
        "query": "how does frontend authenticate to backend",
        "expected": "frontend/tests/Feature/Auth/ApiAuthenticationTest.php",
        "category": "Authentication",
    },
    {
        "id": 3,
        "query": "export to CSV JSON",
        "expected": "frontend/resources/js/Components/TableExport.vue",
        "category": "Import/export",
    },
    {
        "id": 4,
        "query": "VAT calculation",
        "expected": "backend/src/models/account.py",
        "category": "Business logic",
    },
    {
        "id": 5,
        "query": "database connection pool",
        "expected": "backend/src/db/connection.py",
        "category": "Infrastructure",
    },
    # New queries
    {
        "id": 6,
        "query": "invoice list API endpoint",
        "expected": "backend/src/api/routers/invoices.py",
        "category": "API endpoints",
    },
    {
        "id": 7,
        "query": "payment status workflow",
        "expected": "backend/src/ledger/payment_status.py",
        "category": "Payment/billing",
    },
    {
        "id": 8,
        "query": "how are billing runs created",
        "expected": "backend/src/ledger/billing_runs.py",
        "category": "Payment/billing",
    },
    {
        "id": 9,
        "query": "API error response handling",
        "expected": "backend/src/api/middleware.py",
        "category": "Error handling",
    },
    {
        "id": 10,
        "query": "BillingApiException",
        "expected": "frontend/app/Services/BillingApiException.php",
        "category": "Error handling",
    },
]

# Models to benchmark
MODELS = [
    {"name": "baseline", "rerank": False, "model": None},
    {"name": "flashrank", "rerank": True, "model": "flashrank"},
    {"name": "flashrank:mini", "rerank": True, "model": "flashrank:mini"},
    {"name": "voyage", "rerank": True, "model": "voyage"},
    {"name": "voyage:lite", "rerank": True, "model": "voyage:lite"},
    {"name": "minilm", "rerank": True, "model": "minilm"},
    # {"name": "bge-m3", "rerank": True, "model": "bge-m3"},  # Disabled: too slow
]


def run_query(
    query: str,
    repo_path: str,
    rerank: bool = False,
    rerank_model: str | None = None,
    n_results: int = 10,
    rerank_top: int = 50,
) -> dict:
    """Run ogrep query and return results."""
    # Use ogrep from the project's venv to avoid PATH conflicts
    ogrep_bin = Path(__file__).parent.parent / ".venv" / "bin" / "ogrep"
    cmd = [
        str(ogrep_bin),
        "query",
        query,
        "-n",
        str(n_results),
        "--no-cache",  # Disable caching for consistent benchmark results
    ]

    if rerank:
        cmd.append("--rerank")
        if rerank_model:
            cmd.extend(["--rerank-model", rerank_model])
        cmd.extend(["--rerank-top", str(rerank_top)])

    try:
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min for model download on first use
        )
        if result.returncode != 0:
            return {"error": result.stderr, "results": []}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "Timeout", "results": []}
    except json.JSONDecodeError as e:
        return {"error": f"JSON decode error: {e}", "results": []}


def find_file_rank(results: list, expected_file: str) -> int | None:
    """Find the rank (1-indexed) of expected file in results."""
    for i, result in enumerate(results):
        # Try both 'relative_path' (new format) and 'file' (legacy)
        file_path = result.get("relative_path", result.get("file", ""))
        # Match if the file path ends with the expected path
        if file_path.endswith(expected_file) or expected_file in file_path:
            return i + 1
    return None


def calculate_metrics(ranks: list[int | None]) -> dict:
    """Calculate Hit@1, Hit@3, Hit@5, and MRR from ranks."""
    n = len(ranks)

    hit_at_1 = sum(1 for r in ranks if r is not None and r == 1)
    hit_at_3 = sum(1 for r in ranks if r is not None and r <= 3)
    hit_at_5 = sum(1 for r in ranks if r is not None and r <= 5)

    # MRR (Mean Reciprocal Rank)
    mrr_sum = sum(1.0 / r for r in ranks if r is not None)
    mrr = mrr_sum / n if n > 0 else 0.0

    return {
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "hit_at_1_pct": hit_at_1 / n * 100 if n > 0 else 0,
        "hit_at_3_pct": hit_at_3 / n * 100 if n > 0 else 0,
        "hit_at_5_pct": hit_at_5 / n * 100 if n > 0 else 0,
        "mrr": mrr,
        "total": n,
    }


def run_benchmark(repo_path: str, verbose: bool = False) -> dict:
    """Run full benchmark for all models."""
    results = {}

    for model_config in MODELS:
        model_name = model_config["name"]
        print(f"\n{'='*60}")
        print(f"Testing model: {model_name}")
        print(f"{'='*60}")

        model_results = []
        ranks = []

        for gt in GROUND_TRUTH:
            query = gt["query"]
            expected = gt["expected"]

            print(f"  Query {gt['id']}: {query[:40]}...", end=" ", flush=True)

            query_result = run_query(
                query=query,
                repo_path=repo_path,
                rerank=model_config["rerank"],
                rerank_model=model_config["model"],
            )

            if "error" in query_result and query_result["error"]:
                print(f"ERROR: {query_result['error'][:50]}")
                rank = None
            else:
                search_results = query_result.get("results", [])
                rank = find_file_rank(search_results, expected)

                if rank:
                    print(f"rank={rank}")
                else:
                    print("NOT FOUND")
                    if verbose and search_results:
                        top_file = search_results[0].get('relative_path', search_results[0].get('file', 'N/A'))
                        print(f"    Top result: {top_file}")

            ranks.append(rank)
            model_results.append(
                {
                    "query_id": gt["id"],
                    "query": query,
                    "expected": expected,
                    "category": gt["category"],
                    "rank": rank,
                    "found": rank is not None,
                }
            )

        metrics = calculate_metrics(ranks)
        results[model_name] = {
            "config": model_config,
            "queries": model_results,
            "metrics": metrics,
        }

        print(f"\n  Metrics for {model_name}:")
        print(f"    Hit@1: {metrics['hit_at_1']}/{metrics['total']}")
        print(f"    Hit@3: {metrics['hit_at_3']}/{metrics['total']}")
        print(f"    Hit@5: {metrics['hit_at_5']}/{metrics['total']}")
        print(f"    MRR:   {metrics['mrr']:.3f}")

    return results


def generate_quality_report(results: dict, output_path: str) -> None:
    """Generate reranking-quality-benchmark.md report."""
    lines = [
        "# Reranking Quality Benchmark",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "**Codebase:** julan_peppol",
        f"**Queries:** {len(GROUND_TRUTH)}",
        "",
        "## Summary",
        "",
        "| Model | Hit@1 | Hit@3 | Hit@5 | MRR |",
        "|-------|-------|-------|-------|-----|",
    ]

    # Find best model by MRR
    best_model = None
    best_mrr = -1

    for model_name, data in results.items():
        m = data["metrics"]
        mrr = m["mrr"]
        if mrr > best_mrr:
            best_mrr = mrr
            best_model = model_name

        lines.append(
            f"| {model_name} | {m['hit_at_1']}/{m['total']} | "
            f"{m['hit_at_3']}/{m['total']} | {m['hit_at_5']}/{m['total']} | "
            f"{mrr:.3f} |"
        )

    lines.extend(
        [
            "",
            f"**Winner:** {best_model} (MRR {best_mrr:.3f})",
            "",
            "---",
            "",
            "## Per-Query Results",
            "",
        ]
    )

    # Per-query breakdown
    for gt in GROUND_TRUTH:
        lines.extend(
            [
                f"### Query {gt['id']}: \"{gt['query']}\"",
                "",
                f"**Expected:** `{gt['expected']}`",
                f"**Category:** {gt['category']}",
                "",
                "| Model | Rank | Found |",
                "|-------|------|-------|",
            ]
        )

        for model_name, data in results.items():
            query_result = next(
                (q for q in data["queries"] if q["query_id"] == gt["id"]), None
            )
            if query_result:
                rank = query_result["rank"]
                found = "Yes" if query_result["found"] else "No"
                rank_str = str(rank) if rank else "-"
                lines.append(f"| {model_name} | {rank_str} | {found} |")

        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## Metrics Explanation",
            "",
            "- **Hit@K**: Expected file appears in top K results",
            "- **MRR**: Mean Reciprocal Rank = average of 1/rank for each query",
            "  - MRR 1.0 = all queries have correct file at rank 1",
            "  - MRR 0.5 = average rank is 2",
            "",
        ]
    )

    Path(output_path).write_text("\n".join(lines))
    print(f"\nGenerated: {output_path}")


def generate_comparison_report(results: dict, output_path: str) -> None:
    """Generate reranking-vs-openai-baseline.md comparison report."""
    baseline = results.get("baseline", {})
    baseline_queries = {q["query_id"]: q for q in baseline.get("queries", [])}

    # Find best reranking model
    best_model = None
    best_mrr = -1
    for model_name, data in results.items():
        if model_name == "baseline":
            continue
        mrr = data["metrics"]["mrr"]
        if mrr > best_mrr:
            best_mrr = mrr
            best_model = model_name

    if not best_model:
        print("No reranking models found for comparison")
        return

    best_data = results[best_model]
    best_queries = {q["query_id"]: q for q in best_data.get("queries", [])}

    lines = [
        "# Reranking vs OpenAI Baseline Comparison",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Best Reranking Model:** {best_model}",
        "**Baseline:** OpenAI semantic search (no reranking)",
        "",
        "## Summary",
        "",
        "| Metric | Baseline | Best Reranker | Improvement |",
        "|--------|----------|---------------|-------------|",
    ]

    bm = baseline.get("metrics", {})
    rm = best_data.get("metrics", {})

    for metric in ["hit_at_1", "hit_at_3", "hit_at_5", "mrr"]:
        bval = bm.get(metric, 0)
        rval = rm.get(metric, 0)

        if metric == "mrr":
            bstr = f"{bval:.3f}"
            rstr = f"{rval:.3f}"
            diff = rval - bval
            imp = f"+{diff:.3f}" if diff > 0 else f"{diff:.3f}"
        else:
            total = bm.get("total", 10)
            bstr = f"{bval}/{total}"
            rstr = f"{rval}/{total}"
            diff = rval - bval
            imp = f"+{diff}" if diff > 0 else str(diff)

        metric_name = metric.replace("_", "@").upper()
        lines.append(f"| {metric_name} | {bstr} | {rstr} | {imp} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## Per-Query Position Changes",
            "",
            "| # | Query | Baseline Rank | Reranked Rank | Lift |",
            "|---|-------|---------------|---------------|------|",
        ]
    )

    total_lift = 0
    improved = 0
    unchanged = 0
    degraded = 0

    for gt in GROUND_TRUTH:
        qid = gt["id"]
        bq = baseline_queries.get(qid, {})
        rq = best_queries.get(qid, {})

        b_rank = bq.get("rank")
        r_rank = rq.get("rank")

        b_str = str(b_rank) if b_rank else "-"
        r_str = str(r_rank) if r_rank else "-"

        if b_rank and r_rank:
            lift = b_rank - r_rank  # Positive = improvement
            lift_str = f"+{lift}" if lift > 0 else str(lift)
            total_lift += lift
            if lift > 0:
                improved += 1
            elif lift == 0:
                unchanged += 1
            else:
                degraded += 1
        elif r_rank and not b_rank:
            lift_str = "NEW"
            improved += 1
        elif b_rank and not r_rank:
            lift_str = "LOST"
            degraded += 1
        else:
            lift_str = "-"
            unchanged += 1

        query_short = gt["query"][:35] + "..." if len(gt["query"]) > 35 else gt["query"]
        lines.append(f"| {qid} | {query_short} | {b_str} | {r_str} | {lift_str} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## Lift Analysis",
            "",
            f"- **Improved:** {improved}/{len(GROUND_TRUTH)} queries",
            f"- **Unchanged:** {unchanged}/{len(GROUND_TRUTH)} queries",
            f"- **Degraded:** {degraded}/{len(GROUND_TRUTH)} queries",
            f"- **Total position lift:** {total_lift} positions",
            "",
            "---",
            "",
            "## Recommendation",
            "",
        ]
    )

    mrr_improvement = rm.get("mrr", 0) - bm.get("mrr", 0)
    if mrr_improvement > 0.05:
        lines.append(
            f"**Strong recommendation to use {best_model} reranking.** "
            f"MRR improved by {mrr_improvement:.3f} ({mrr_improvement*100:.1f}%)."
        )
    elif mrr_improvement > 0:
        lines.append(
            f"**Mild recommendation to use {best_model} reranking.** "
            f"MRR improved by {mrr_improvement:.3f}, but gains are modest."
        )
    else:
        lines.append(
            "**Reranking does not improve results** for this query set. "
            "OpenAI semantic search is sufficient."
        )

    lines.append("")

    Path(output_path).write_text("\n".join(lines))
    print(f"Generated: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Reranking Quality Benchmark")
    parser.add_argument(
        "--repo",
        default="/home/glenn/repos/julan_peppol",
        help="Path to repository to benchmark",
    )
    parser.add_argument(
        "--output-dir",
        default="/home/glenn/repos/ogrep/test-reports",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw results as JSON",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("RERANKING QUALITY BENCHMARK")
    print("=" * 60)
    print(f"Repository: {args.repo}")
    print(f"Ground truth queries: {len(GROUND_TRUTH)}")
    print(f"Models to test: {len(MODELS)}")

    # Run benchmark
    results = run_benchmark(args.repo, verbose=args.verbose)

    # Output JSON if requested
    if args.json:
        print("\n" + json.dumps(results, indent=2))

    # Generate reports
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generate_quality_report(
        results, str(output_dir / "reranking-quality-benchmark.md")
    )
    generate_comparison_report(
        results, str(output_dir / "reranking-vs-openai-baseline.md")
    )

    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
