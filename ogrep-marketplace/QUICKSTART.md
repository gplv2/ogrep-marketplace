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


# Optional MCP wrapper:

```
pip install -e ".[mcp]"
python -m ogrep.mcp
```

