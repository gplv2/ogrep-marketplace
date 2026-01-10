# Quick start after unzip:

```
unzip ogrep_repo_skeleton.zip
cd ogrep_repo_skeleton
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
export OPENAI_API_KEY="..."

ogrep index .
ogrep query "where is X implemented?" --top 15
```

# Dev
## 1) Create a fresh venv for this repo (recommended at repo root)
cd ~/repos/ogrep
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip

## 2) Install your package from the directory that has pyproject.toml

cd ~/repos/ogrep/ogrep-marketplace
python -m pip install -e .

hash -r 2>/dev/null || true
which ogrep
ogrep --help

If which ogrep still shows nothing, run:
```
python -m pip show ogrep
python -c "import sys; print(sys.executable)"
```

## 3) Add a quick “activation helper” (so you don’t repeat yourself)

Create ~/repos/ogrep/activate.sh:

```
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
. .venv/bin/activate
cd ogrep-marketplace
```
Then:

```
chmod +x ~/repos/ogrep/activate.sh
./activate.sh
ogrep --help

```



# Optional MCP wrapper:

```
pip install -e ".[mcp]"
python -m ogrep.mcp
```

