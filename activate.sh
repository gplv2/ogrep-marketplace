#!/usr/bin/env bash
# ogrep development environment activation
# Usage: source activate.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Load .env if present (KEY=VALUE lines)
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1090
    source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env)
    set +a
    echo "Loaded .env"
fi

# Create venv if it doesn't exist
if [[ ! -d .venv ]]; then
    echo "Creating .venv..."
    python3 -m venv .venv
fi

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

# Install in editable mode if not already installed
if ! command -v ogrep &> /dev/null; then
    echo "Installing ogrep in editable mode..."
    pip install -e ".[dev]" > /dev/null
fi

echo "ogrep development environment activated"
echo "Run 'ogrep --help' to get started"
