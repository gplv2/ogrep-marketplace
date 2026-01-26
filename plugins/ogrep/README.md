# ogrep Plugin for Claude Code

Semantic code search with hybrid search modes (semantic, fulltext, hybrid).

## Setup

### 1. Install ogrep

```bash
pip install ogrep
```

For Voyage AI (recommended for code):
```bash
pip install "ogrep[voyage]"
```

### 2. Configure API Keys

Claude Code needs access to your API keys. Copy the example settings and add your keys:

```bash
cp .claude/settings.json.example .claude/settings.local.json
```

Then edit `.claude/settings.local.json` with your actual keys:

```json
{
  "env": {
    "VOYAGE_API_KEY": "pa-your-actual-key",
    "OPENAI_API_KEY": "sk-your-actual-key"
  }
}
```

**Note:** You only need ONE of these keys:
- `VOYAGE_API_KEY` - For Voyage AI (code-optimized, recommended)
- `OPENAI_API_KEY` - For OpenAI embeddings

### 3. Index your codebase

```bash
ogrep index .
```

## Usage

The plugin provides skills that Claude will automatically use for code search queries like:
- "where is authentication handled"
- "how does the API work"
- "find the database connection code"

## Manual Commands

```bash
ogrep query "your search"           # Hybrid search (default)
ogrep query "auth" --mode semantic  # Conceptual search
ogrep query "def foo" --mode fulltext  # Exact match
ogrep chunk "file.py:5" -C 1        # Expand context
```
