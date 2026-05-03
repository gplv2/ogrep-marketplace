## API Key Configuration

ogrep needs at least one API key for embeddings. There are three ways to provide it, in priority order:

### Option 1: `.env` file in your project (recommended)

Create a `.env` file in your project root:

```bash
# .env — add to .gitignore!
VOYAGE_API_KEY=pa-your-key
# or
OPENAI_API_KEY=sk-your-key
```

This works everywhere:
- **CLI:** ogrep loads `.env` via python-dotenv
- **MCP server:** The MCP server loads `.env` from the project root at startup (v0.10.3+)
- **Claude Code Bash commands:** Use with `direnv` or `activate.sh` to export into the shell

**Why this is recommended:** Standard Python convention. Works for both CLI and MCP. The `.env` file is per-project and goes in `.gitignore`.

### Option 2: Claude Code settings (Claude Code only)

Claude Code injects `env` from settings into all child processes (including MCP servers).

**Project-level** — `.claude/settings.local.json`:

```bash
cp .claude/settings.json.example .claude/settings.local.json
# Edit and add your actual API keys
```

Or create directly:

```bash
cat << EOF > .claude/settings.local.json
{
  "env": {
    "VOYAGE_API_KEY": "$VOYAGE_API_KEY",
    "OPENAI_API_KEY": "$OPENAI_API_KEY"
  }
}
EOF
```

**User-level** (all projects) — `~/.claude/settings.json`:

```json
{
  "env": {
    "OPENAI_API_KEY": "sk-your-key",
    "VOYAGE_API_KEY": "pa-your-key"
  }
}
```

### Option 3: Shell environment variables

```bash
export VOYAGE_API_KEY=pa-your-key
```

Works for CLI. For Claude Code, shell vars from `.bashrc`/`.zshrc` are **not inherited** by non-interactive sessions — use Option 1 or 2 instead.

### Priority order

When multiple sources provide the same key, explicit env vars win:

1. Shell environment (highest)
2. Claude Code settings (`settings.local.json`)
3. `.env` file in project root (lowest, `override=False`)

### Settings Template

See `.claude/settings.json.example` for all available environment variables. Convention:
- Keys starting with `_` are disabled (commented out)
- Remove the `_` prefix to enable a setting

---

## Updating the Plugin

Claude Code caches plugins at install time. After a new ogrep release, the cache still has the old version — `/plugin` will report "already at latest" even though it's stale.

### Fix: Nuke cache and reinstall

```bash
rm -rf ~/.claude/plugins/cache/ogrep-marketplace
```

Then restart Claude Code and reinstall:
```
/plugin install ogrep@ogrep-marketplace
```

### For developers: Symlink instead of cache

If you're developing ogrep or want to always run from your local checkout:

```bash
rm -rf ~/.claude/plugins/cache/ogrep-marketplace/ogrep
ln -s ~/repos/ogrep-marketplace/plugins/ogrep ~/.claude/plugins/cache/ogrep-marketplace/ogrep
```

This way Claude Code always loads your local dev copy — no more stale cache. Changes to plugin files (agent, skill, plugin.json) take effect on the next Claude Code restart.

### Verify

After updating, check that the MCP server is registered:
```bash
cat ~/.claude/plugins/cache/ogrep-marketplace/ogrep/.claude-plugin/plugin.json | grep version
# Should show the latest version with mcpServers
```

In Claude Code, `/mcp` should list the ogrep server.

---

## Auto-Allow ogrep Commands (Optional)

To let Claude Code run ogrep commands without prompting each time, add this to your settings:

**Project-level** (`.claude/settings.json` - shareable with team):
```json
{
  "permissions": {
    "allow": [
      "Bash(ogrep:*)",
      "Skill(ogrep:*)"
    ]
  }
}
```

**User-level** (`~/.claude/settings.json` - all your projects):
```json
{
  "permissions": {
    "allow": [
      "Bash(ogrep:*)",
      "Skill(ogrep:*)"
    ]
  }
}
```

Or run interactively:
```
/permissions add Bash(ogrep:*)
/permissions add Skill(ogrep:*)
```

## Bash Sandboxing

### What is Claude Code Sandboxing?

Sandboxing is a security feature that creates isolated boundaries for Claude Code's bash commands, so it can work more autonomously without constant permission prompts.

### Two Boundaries

- Filesystem Isolation: Claude can only write to the current working directory. Can read most of your system (except sensitive dirs like ~/.ssh, ~/.aws). Cannot modify files outside your project.
- Network Isolation: All network traffic goes through a proxy. Only approved domains can be accessed. Claude cannot exfiltrate data to random servers.

Why Both Matter

Without network isolation: A compromised Claude could steal your SSH keys and send them to an attacker
Without filesystem isolation: A compromised Claude could modify ~/.bashrc to gain persistent access

## How to Enable

/sandbox

{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "excludedCommands": ["docker", "git"]
  }
}


The Big Win: 84% Fewer Permission Prompts
In our internal usage, we've found that sandboxing safely reduces permission prompts by 84%.
For Your ogrep Use Case
If you enable sandboxing with autoAllowBashIfSandboxed: true, then ogrep commands would auto-run as long as they don't need network access.
But here's the catch: ogrep needs network access for OpenAI embeddings (unless you use local embeddings with LM Studio). So you'd need to either:

Add OpenAI's API domain to the allowed network list
Use local embeddings (OGREP_BASE_URL)
Or just use the simpler permission allowlist approach I showed earlier:

{
  "permissions": {
    "allow": ["Bash(ogrep:*)"]
  }
}

Bottom line: Sandboxing is great for general security, but for ogrep specifically, the simpler "allow": ["Bash(ogrep:*)"] permission rule is probably more practical since ogrep is a known, trusted tool.





Option 2: Exclude ogrep from sandbox entirely
If ogrep needs network access and you trust it, just exclude it:
json{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "excludedCommands": ["git", "docker", "ogrep"]
  },
  "permissions": {
    "allow": [
      "Bash(ogrep:*)"
    ]
  }
}




Option 1: WebFetch Allow Rules (for network domains)
json{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "excludedCommands": ["git", "docker"]
  },
  "permissions": {
    "allow": [
      "WebFetch(api.openai.com)",
      "WebFetch(*.openai.com)"
    ]
  }
}




This way:

ogrep runs outside the sandbox (so it can reach OpenAI)
Bash(ogrep:*) auto-allows it without prompts
Other bash commands stay sandboxed

Option 3: Skip sandbox, just use permissions (simplest)
If you don't need full sandboxing, just use the permission allowlist:

{
  "permissions": {
    "allow": [
      "Bash(ogrep:*)",
      "Skill(ogrep:*)"
    ]
  }
}
