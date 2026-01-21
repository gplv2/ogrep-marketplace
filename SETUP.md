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
