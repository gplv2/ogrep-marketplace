---
name: semantic-grep
description: Semantic grep for a repo. Use when the user asks to "search by meaning", "find where this is implemented", "grep semantically", "where is this handled", or when exact grep is not enough.
allowed-tools: Bash, Read
---

# Semantic grep workflow (ogrep)

You can do fast semantic search over the local repo using `ogrep` (SQLite index + OpenAI embeddings).

## Rules
1. Prefer `ogrep query` before manual ripgrep when the user intent is conceptual.
2. If the repo is not indexed yet, run `ogrep index .` first.
3. Use the results to open the top files and then proceed with normal code reasoning.

## Commands

Index (creates `.ogrep/index.sqlite`):
- `ogrep index .`

Query:
- `ogrep query "<natural language query>" --top 15`

## Operational notes
- Requires `OPENAI_API_KEY` in the environment for embeddings.
- Indexing sends chunk text to the embeddings API; keep chunk sizes reasonable.

