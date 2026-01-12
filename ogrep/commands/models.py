"""
Models command for ogrep.

Lists available OpenAI embedding models with their characteristics,
pricing, and recommended use cases.
"""

from __future__ import annotations

import argparse
import json

from ..models import format_models_table, list_models


def cmd_models(args: argparse.Namespace) -> int:
    """
    Display available embedding models.

    Shows a formatted table of all supported OpenAI embedding models
    with their dimensions, pricing, and use cases.

    Args:
        args: Parsed command-line arguments containing:
            - json: Whether to output as JSON

    Returns:
        Exit code (0 for success).
    """
    use_json = getattr(args, "json", False)

    if use_json:
        models = list_models()
        output = {
            "models": [
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "dimensions": m.dimensions,
                    "max_dimensions": m.max_dimensions,
                    "price_per_million": m.price_per_million,
                    "use_cases": list(m.use_cases),
                    "notes": m.notes,
                    "optimal_chunk_lines": m.optimal_chunk_lines,
                    "optimal_overlap_lines": m.optimal_overlap_lines,
                    "context_tokens": m.context_tokens,
                    "max_batch_size": m.max_batch_size,
                }
                for m in models
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_models_table())

    return 0
