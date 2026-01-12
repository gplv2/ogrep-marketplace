# ogrep v0.6.4 Release Notes

## What's New

### Relative Confidence Scoring (Default)

Confidence levels now use **relative scoring** by default. Instead of comparing scores against fixed thresholds, each result is compared to the top score. This provides much more meaningful confidence levels.

**The Problem (Old Behavior):**
Cosine similarity scores for text embeddings cluster around 0.3-0.5, not uniformly across [0,1]. A score of 0.45 is actually excellent, but the old threshold of 0.85 for "high" confidence was rarely achievable.

```bash
# Old absolute scoring (misleading):
  1. src/auth.py:2  score=0.45 [very_low]  # Actually a great match!
```

**The Solution (New Behavior):**
Relative scoring compares each result to the best result:

```bash
# New relative scoring (accurate):
  1. src/auth.py:2  score=0.45 [high]      # Top result = high confidence
  2. src/auth.py:5  score=0.42 [high]      # 93% of top = still high
  3. src/utils.py:1 score=0.35 [medium]    # 78% of top = medium
```

**Relative Thresholds:**
| Confidence | Threshold | Meaning |
|------------|-----------|---------|
| `high` | 90%+ of top | Trust and use directly |
| `medium` | 75-89% | Use but verify context |
| `low` | 50-74% | Consider alternatives |
| `very_low` | <50% | Probably not relevant |

### Environment Variables

```bash
# Relative mode thresholds (default mode)
export OGREP_RELATIVE_HIGH=0.90    # 90% of top score
export OGREP_RELATIVE_MEDIUM=0.75  # 75% of top score
export OGREP_RELATIVE_LOW=0.50     # 50% of top score

# Switch to absolute mode if needed
export OGREP_CONFIDENCE_MODE=absolute

# Absolute thresholds (recalibrated in v0.6.4)
export OGREP_CONFIDENCE_HIGH=0.50   # Was 0.85
export OGREP_CONFIDENCE_MEDIUM=0.40 # Was 0.70
export OGREP_CONFIDENCE_LOW=0.30    # Was 0.50
```

## Quick Examples

```bash
# Search by concept (semantic)
ogrep query "where is authentication handled" -n 10 --refresh --json

# Search by exact identifier (fulltext)
ogrep query "def validate_token" --mode fulltext --json

# Combined search (hybrid - default)
ogrep query "user login validation" -n 15 --refresh --json

# Get chunk by reference (after finding in query results)
ogrep chunk "src/auth.py:2" --json

# Expand context around a result
ogrep chunk "src/auth.py:2" --context 1 --json

# Index the repo (first time or after major changes)
ogrep index .

# Check index status
ogrep status --json
```

## Common Patterns

| Task | Command |
|------|---------|
| Find where X is implemented | `ogrep query "where is X handled" --json` |
| Find exact function/class | `ogrep query "def function_name" --mode fulltext --json` |
| Understand how X works | `ogrep query "how does X work" -n 15 --json` |
| Find all uses of X | `ogrep query "X" --mode fulltext --json` |
| Search after editing files | `ogrep query "..." --refresh --json` |
| Get more context | `ogrep chunk "file.py:N" --context 2` |

## Chunk Navigation

After a query finds something interesting, use `ogrep chunk` to expand context:

```bash
# Get chunk by reference (from query results)
ogrep chunk "src/auth.py:2"

# Get surrounding context
ogrep chunk "src/auth.py:2" --before 1    # + 1 chunk before
ogrep chunk "src/auth.py:2" --after 1     # + 1 chunk after
ogrep chunk "src/auth.py:2" --context 1   # + 1 before AND after

# Also works with raw chunk IDs
ogrep chunk 42
```

## Upgrading

```bash
pip install --upgrade ogrep
# or
pip install --force-reinstall git+https://github.com/gplv2/ogrep.git
```

No reindex needed - relative scoring works with existing indexes.

## Documentation

- [README.md](README.md) - Quick start and overview
- [LOCAL_EMBEDDINGS_GUIDE.md](LOCAL_EMBEDDINGS_GUIDE.md) - Detailed local model setup
- [CHANGELOG.md](CHANGELOG.md) - Full technical changelog

## Links

- GitHub: https://github.com/gplv2/ogrep-marketplace
