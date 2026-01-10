#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Load .env if present (KEY=VALUE lines)
if [[ -f .env ]]; then
  set -a
  source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env)
  set +a
fi

# Activate repo-local venv
if [[ ! -d .venv ]]; then
  echo "Missing .venv. Create it with: python3 -m venv .venv" >&2
  exit 1
fi
source .venv/bin/activate

# Optional: install/update editable package if not installed yet
python -m pip install -e ./ogrep-marketplace >/dev/null

cd ogrep-marketplace
