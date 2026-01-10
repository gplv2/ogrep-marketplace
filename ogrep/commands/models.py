"""
Models command for ogrep.

Lists available OpenAI embedding models with their characteristics,
pricing, and recommended use cases.
"""

from __future__ import annotations

import argparse

from ..models import format_models_table


def cmd_models(args: argparse.Namespace) -> int:
    """
    Display available embedding models.

    Shows a formatted table of all supported OpenAI embedding models
    with their dimensions, pricing, and use cases.

    Args:
        args: Parsed command-line arguments (currently unused).

    Returns:
        Exit code (0 for success).
    """
    print(format_models_table())
    return 0
