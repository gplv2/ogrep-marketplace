# ogrep

Local semantic "grep" powered by:
- Local SQLite index (`.ogrep/index.sqlite` by default)
- OpenAI embeddings (used only to vectorize chunks)

## Install

Requirements:
- Python 3.10+
- `OPENAI_API_KEY` in your environment

Recommended:
```bash
pipx install ogrep
export OPENAI_API_KEY="..."
```

Or:
```bash
pip install ogrep
export OPENAI_API_KEY="..."
```

Optional extras:
```bash
pip install "ogrep[speed]"   # faster scoring with numpy
pip install "ogrep[mcp]"     # enable MCP server wrapper
```

## CLI

Index a directory (creates `.ogrep/index.sqlite`):
```bash
ogrep index .
```

Query:
```bash
ogrep query "where is invoice status handled?" --top 15
```

Common flags:
```bash
ogrep index . --db .ogrep/index.sqlite
ogrep query "device_number_map" --db .ogrep/index.sqlite --top 25
```

Output is grep-friendly:
- `path:start_line-end_line  score=...`
- followed by a short snippet

## SQLite schema (high level)

The index is a single SQLite file.

- `files`
  - One row per indexed file: `path`, `mtime_ns`, `size`, `sha256`
  - Used to skip unchanged files

- `chunks`
  - One row per chunk: `file_id`, `chunk_index`, `start_line`, `end_line`, `text`
  - Stores embedding as a float32 BLOB + `dim` + `model`

## Claude Code Skill behavior

A Claude Code Skill can call `ogrep` via Bash:
- If `.ogrep/index.sqlite` is missing, run: `ogrep index .`
- For semantic questions, run: `ogrep query "<question>" --top 15`
- Then open the top hits and answer with paths + line ranges

Minimal SKILL.md example is included below in this README (copy/paste).

### Minimal SKILL.md (copy/paste)
Create: `~/.claude/skills/ogrep/SKILL.md`

```md
---
name: ogrep
description: Semantic grep using local SQLite + OpenAI embeddings via the `ogrep` CLI.
allowed-tools: Bash, Read
---

Use `ogrep` for meaning-based searches.

If `.ogrep/index.sqlite` doesn't exist:
- ogrep index .

Then:
- ogrep query "<question>" --top 15
```

## Marketplace / plugin install (optional)

If you later add a Claude marketplace to this repo, it typically looks like:
- `.claude-plugin/marketplace.json` at repo root
- `plugins/<plugin-name>/.claude-plugin/plugin.json`

Then, inside Claude Code:
- `/plugin marketplace add OWNER/REPO`
- `/plugin install <plugin>@<marketplace-name>`

This skeleton repo focuses on pip-first. You can add the marketplace later without changing the CLI.

## MCP wrapper (optional)

If installed with the `mcp` extra:
```bash
pip install "ogrep[mcp]"
python -m ogrep.mcp
```

This starts a local MCP server (stdio transport) exposing:
- `ogrep_index(path, db)`
- `ogrep_search(q, db, top_k)`
