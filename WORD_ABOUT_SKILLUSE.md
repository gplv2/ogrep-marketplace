# using the skill
doing it yourself is really easy, use the skills command or the executable ...

But asking claude this:
  ❯ how will this skill (ogrep) be selected or used in the current setup, imagine we'll add functionality.  will you use this ?

- Honest assessment of how I'd use ogrep in practice:

```
  Current behavior:
  ┌────────────────────────────────────────┬─────────────────────────┬─────────────────────────────┐
  │               Situation                │   What I'd likely use   │             Why             │
  ├────────────────────────────────────────┼─────────────────────────┼─────────────────────────────┤
  │ "Find class Foo"                       │ Grep or Glob            │ Exact match, fast           │
  ├────────────────────────────────────────┼─────────────────────────┼─────────────────────────────┤
  │ "Where is authentication handled?"     │ Task with Explore agent │ System prompt recommends it │
  ├────────────────────────────────────────┼─────────────────────────┼─────────────────────────────┤
  │ "How does billing work?"               │ Task with Explore agent │ Open-ended exploration      │
  ├────────────────────────────────────────┼─────────────────────────┼─────────────────────────────┤
  │ User explicitly says "semantic search" │ ogrep                   │ Direct request              │
  └────────────────────────────────────────┴─────────────────────────┴─────────────────────────────┘
```

##  The gap: I'd probably underuse ogrep because:
  1. The Explore agent is explicitly recommended for "open-ended" questions
  2. Grep/Glob are my default for searching
  3. ogrep requires a separate Bash call or skill invocation

## When ogrep would actually be better:
  - Conceptual queries where I don't know the exact terms ("where is error recovery handled")
  - Finding implementations by intent rather than name
  - Quick semantic lookup before spawning a heavier Explore agent

## To increase adoption, you could:

  1. Add to CLAUDE.md - A note like "Use ogrep query for semantic code search before spawning Explore agents"
  2. Make it a proactive skill - Update the skill description to say it should be used proactively for conceptual questions
  3. Integrate with Explore agent - Have the Explore agent use ogrep internally as one of its search strategies

# try to do this

## Ask claude

put something like this in CLAUDE.md

```
### Code Search
Use `ogrep query "<question>"` for semantic code search before spawning Explore agents.

**When to use ogrep:**
- Conceptual questions: "where is error handling done", "how does authentication work"
- Finding implementations by intent rather than exact name
- Quick lookup when you don't know the exact terms used in the codebase

**When to use Grep/Glob instead:**
- Exact matches: class names, function names, specific strings
- Known patterns: `class Foo`, `def bar`, `import xyz`

**Examples:**
```bash
# Semantic search (use ogrep)
ogrep query "how are invoices validated before sending"
ogrep query "where is the billing period calculated"

# Exact search (use Grep)
grep "class InvoiceGenerator"
grep "def generate_invoice"
```

## Make it proactive
