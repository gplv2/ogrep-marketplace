# ogrep Plugin for Claude Code

Semantic code search with MCP server and agentic search agent.

## Setup

### 1. Install ogrep

```bash
pip install "ogrep[ast,mcp]"
```

For Voyage AI (recommended for code):
```bash
pip install "ogrep[ast,voyage,mcp]"
```

### 2. Configure API Keys

Create a `.env` file in your project root:

```bash
# .env — add to .gitignore!
VOYAGE_API_KEY=pa-your-key
# or
OPENAI_API_KEY=sk-your-key
```

The MCP server loads this automatically. You only need **one** of these keys.

**Alternative:** Configure in Claude Code settings (`.claude/settings.local.json`):

```json
{
  "env": {
    "VOYAGE_API_KEY": "pa-your-actual-key"
  }
}
```

### 3. Index your codebase

```bash
ogrep index .
```

## How It Works

The plugin provides three layers:

- **MCP server** — 5 native tools (`ogrep_query`, `ogrep_chunk`, `ogrep_index`, `ogrep_status`, `ogrep_health`) that Claude calls directly as first-class tools
- **Search agent** — Dispatched automatically for conceptual code questions, runs a summarize-narrow-drill workflow through MCP tools
- **Skill** — Routing layer that tells Claude *when* to use ogrep

## Usage

Claude automatically uses ogrep for code search queries like:
- "where is authentication handled"
- "how does the API work"
- "find the database connection code"

For simple queries, Claude can call MCP tools directly:
- `ogrep_query("where is auth?")` — quick search
- `ogrep_status()` — check index info

## CLI Commands

```bash
ogrep query "your search"           # Hybrid search (default)
ogrep query "auth" --mode semantic  # Conceptual search
ogrep query "def foo" --mode fulltext  # Exact match
ogrep chunk "file.py:5" -C 1        # Expand context
ogrep status                         # Index stats
```
