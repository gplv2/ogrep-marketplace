# Local Embeddings Guide: Tuning & Testing

This guide documents real-world observations from testing local embedding models with ogrep. It covers model installation, performance characteristics, optimal chunk sizes, and troubleshooting.

## Table of Contents

- [Overview](#overview)
- [Installing LM Studio](#installing-lm-studio)
- [Downloading Embedding Models](#downloading-embedding-models)
- [Model Comparison: Nomic vs BGE](#model-comparison-nomic-vs-bge)
- [Chunk Size Tuning](#chunk-size-tuning)
- [Query Quality Analysis](#query-quality-analysis)
- [Recommendations](#recommendations)
- [Troubleshooting](#troubleshooting)

---

## Overview

Local embedding models allow you to run semantic search without sending data to OpenAI. Benefits include:

- **Privacy**: Your code never leaves your machine
- **Cost**: Zero API costs ($0.00/M tokens)
- **Offline**: Works without internet connection
- **Speed**: No network latency (though embedding generation may be slower)

However, local models have different characteristics than OpenAI models, and **optimal settings vary significantly between models**.

---

## Installing LM Studio

LM Studio is a desktop application that runs local AI models and exposes an OpenAI-compatible API.

### Step 1: Download LM Studio

Download from [lmstudio.ai](https://lmstudio.ai/):

| Platform | Installation |
|----------|--------------|
| **macOS** | Download DMG, drag to Applications |
| **Linux** | Download AppImage, `chmod +x`, run |
| **Windows** | Download EXE installer, run |

**System Requirements:**
- 16GB RAM minimum (embedding models are small, ~100-200MB)
- macOS 13.6+, Windows 10+, or Ubuntu 22.04+

### Step 2: Launch LM Studio Once

**Critical:** You must launch LM Studio at least once before the CLI works. This creates the `~/.lmstudio/` directory (or `~/.cache/lm-studio/` on some systems).

```bash
# Linux example
chmod +x ~/Downloads/LM-Studio-*.AppImage
~/Downloads/LM-Studio-*.AppImage
# Wait for it to fully initialize, then close it
```

### Step 3: Add CLI to PATH

The `lms` CLI ships with LM Studio. Add it to your PATH:

```bash
# Find where LM Studio installed
cat ~/.lmstudio-home-pointer
# Output example: /home/user/.cache/lm-studio

# Bootstrap the CLI (adds to PATH)
~/.cache/lm-studio/bin/lms bootstrap
# Or: ~/.lmstudio/bin/lms bootstrap

# Follow prompts, then reload shell
source ~/.bashrc

# Verify
lms --version
```

### Step 4: Start the Server

```bash
lms server start --port 1234
lms status  # Should show "Server: ON (port: 1234)"
```

---

## Downloading Embedding Models

LM Studio can download models directly from HuggingFace.

### Available Embedding Models

| Model | Command | Size | Dimensions | Notes |
|-------|---------|------|------------|-------|
| **nomic-embed-text-v1.5** | `lms get nomic-embed-text-v1.5` | 84 MB (Q4) | 768 | Good general-purpose, prefers larger chunks |
| **bge-base-en-v1.5** | `lms get bge-base-en-v1.5` | 118 MB (Q8) | 768 | Higher quality quantization, prefers smaller chunks |
| **all-MiniLM-L6-v2** | `lms get all-MiniLM-L6-v2` | 25 MB (Q8) | 384 | Smallest, fastest, excellent accuracy with small chunks |

### Download Commands

```bash
# Download nomic (recommended starting point)
lms get nomic-embed-text-v1.5 -y

# Download BGE
lms get bge-base-en-v1.5 -y

# Download MiniLM (smallest, fastest)
lms get all-MiniLM-L6-v2 -y

# List downloaded models
lms ls
```

**Example output:**
```
You have 3 models, taking up 227.09 MB of disk space.

EMBEDDING                                    PARAMS    ARCH          SIZE
text-embedding-all-minilm-l6-v2-embedding    22M       BERT          25.01 MB
text-embedding-bge-base-en-v1.5              109M      BERT          117.97 MB
text-embedding-nomic-embed-text-v1.5                   Nomic BERT    84.11 MB
```

### Loading Models

```bash
# Load nomic
lms load nomic-ai/nomic-embed-text-v1.5-GGUF -y

# Load BGE
lms load bge-base-en-v1.5 -y

# Load MiniLM
lms load all-minilm-l6-v2 -y

# Check what's loaded
lms status
```

**Note:** The model name for `lms load` may differ from `lms get`. Use `lms ls` to see exact names, or run `lms load` without `-y` to select interactively.

---

## Model Comparison

We tested three local models on the ogrep codebase (29 source files, ~52-79 chunks depending on chunk size).

### Key Differences

| Characteristic | nomic-embed-text-v1.5 | bge-base-en-v1.5 | all-MiniLM-L6-v2 |
|----------------|----------------------|------------------|------------------|
| **Architecture** | Nomic BERT | BERT | BERT |
| **Size** | 84 MB (Q4_K_M) | 118 MB (Q8_0) | 25 MB (Q8_0) |
| **Dimensions** | 768 | 768 | 384 |
| **Optimal chunk size** | 90 lines | 30 lines | 30 lines |
| **Peak accuracy** | 72% | 52% | 96% |
| **Best for** | Larger context windows | Focused, small chunks | Speed + accuracy |

### Performance Observations

**nomic-embed-text-v1.5:**
- Excels with larger chunks (90-120 lines)
- Captures broader context well
- Better at finding the "right file" for conceptual queries
- More forgiving of chunk boundary placement

**bge-base-en-v1.5:**
- Performs best with small chunks (30 lines)
- **Completely fails at larger chunk sizes** (0% accuracy at 90+ lines)
- Higher raw similarity scores but doesn't always find the most relevant content
- More sensitive to exact text matching

**all-MiniLM-L6-v2:**
- Smallest model (~25MB), fastest inference
- Excellent accuracy with small chunks (96% at 30 lines)
- Lower dimensions (384) but still very effective
- Great choice when speed and size matter

---

## Chunk Size Tuning

**This is the most critical finding:** Different embedding models have dramatically different optimal chunk sizes.

### Tuning Results: nomic-embed-text-v1.5

```
Chunk Size   Accuracy   Hits
------------------------------
30           0.32       2/5
45           0.56       4/5
60           0.36       3/5
90           0.72       5/5     <-- OPTIMAL
120          0.68       5/5
```

**Observation:** Nomic improves dramatically with larger chunks. The jump from 60→90 lines is significant (36%→72%).

### Tuning Results: bge-base-en-v1.5

```
Chunk Size   Accuracy   Hits
------------------------------
30           0.52       4/5     <-- OPTIMAL
45           0.40       2/5
60           0.28       2/5
90           0.00       0/5     <-- COMPLETE FAILURE
120          0.00       0/5     <-- COMPLETE FAILURE
```

**Observation:** BGE degrades rapidly as chunk size increases. At 90+ lines, it finds **zero** correct results. This is a critical failure mode to be aware of.

### Tuning Results: all-MiniLM-L6-v2

```
Chunk Size   Accuracy   Hits
------------------------------
30           0.96       5/5     <-- OPTIMAL
45           0.84       5/5
60           0.56       4/5
90           0.68       4/5
120          0.36       2/5
```

**Observation:** MiniLM achieves the highest peak accuracy (96%) of all tested local models at 30-line chunks. Despite having smaller dimensions (384 vs 768), it outperforms both nomic and bge on this codebase. It degrades at larger chunk sizes but less catastrophically than BGE.

### Why This Happens

1. **Training data differences**: Models are trained on different corpus sizes and chunk lengths
2. **Attention mechanisms**: Smaller models may struggle to attend to relevant parts of longer text
3. **Embedding space geometry**: The way models map text to vectors differs; some compress long text poorly
4. **Quantization effects**: Q4 vs Q8 quantization may affect how well context is preserved

### How to Tune for Your Codebase

The model-specific defaults are just starting points. **Your codebase will likely have different optimal settings.** Always run tuning when switching models or on a new repository:

```bash
# Set your base URL
export OGREP_BASE_URL=http://localhost:1234/v1

# Run tuning with the model you plan to use
ogrep tune . -m nomic --samples 10  # Use 10 samples for more reliable results

# Option 1: Save to .env (recommended)
ogrep tune . -m nomic --samples 10 --save
# Creates/updates .env with: OGREP_CHUNK_LINES=<optimal>

# Option 2: Apply immediately and reindex
ogrep tune . -m nomic --samples 10 --apply

# Option 3: Save AND apply
ogrep tune . -m nomic --samples 10 --save --apply
```

### Tune Command Options

| Flag | Description |
|------|-------------|
| `--samples N`, `-s N` | Number of code patterns to test (default: 5, recommend: 10+) |
| `--save` | Save optimal chunk size to `.env` as `OGREP_CHUNK_LINES` |
| `--apply`, `-a` | Reindex immediately with optimal settings |
| `--model M`, `-m M` | Model to test with |

### Understanding --save vs --apply

These flags serve different purposes and can be combined:

| Flag | What it does |
|------|--------------|
| `--save` | Writes `OGREP_CHUNK_LINES=N` to `.env` file (for future indexes) |
| `--apply` | Immediately reindexes with optimal chunk size |

**Use cases:**

```bash
# Just save for later (don't reindex now)
ogrep tune . -m nomic --save

# Reindex now but don't persist setting
ogrep tune . -m nomic --apply

# Both: save AND reindex immediately
ogrep tune . -m nomic --save --apply
```

Without `--apply`, you'd need to manually run `ogrep reindex .` afterward if you want to use the tuned settings right away.

### Environment Variable Priority

When indexing, chunk size is determined in this order:
1. `--chunk-lines` command-line argument (explicit override)
2. `OGREP_CHUNK_LINES` environment variable (your tuned value)
3. Model-specific default (starting point)

**Tip:** Use `--samples 10` or higher for more statistically significant results. The default 5 samples can be noisy.

---

## Query Quality Analysis

We tested identical queries on all models to compare result quality.

### Test Queries and Results

#### Query 1: "how are embeddings cached and reused"

| Model | Top Result | Score | Correct? |
|-------|------------|-------|----------|
| **OpenAI** | `indexer.py:401` (actual cache logic) | 0.57 | ✅ Yes |
| **Nomic** | `indexer.py:401` (actual cache logic) | 0.75 | ✅ Yes |
| **BGE** | `__init__.py:1` (package overview) | 0.68 | ❌ No |
| **MiniLM** | `indexer.py:281` (IndexStats class) | 0.41 | ⚠️ Partial |

**Winner: OpenAI & Nomic** - Both found the actual caching implementation.

#### Query 2: "what files are excluded from indexing"

| Model | Top Result | Score | Correct? |
|-------|------------|-------|----------|
| **OpenAI** | `indexer.py:51` (DEFAULT_EXCLUDES list) | 0.55 | ✅ Yes |
| **Nomic** | `test_embedding_reuse.py:241` | 0.66 | ✅ Relevant |
| **BGE** | `test_embedding_reuse.py:241` | 0.74 | ✅ Relevant |
| **MiniLM** | `indexer.py:241` (iter_files with exclude) | 0.57 | ✅ Yes |

**Winner: OpenAI** - Found the actual DEFAULT_EXCLUDES definition.

#### Query 3: "how does the CLI parse arguments"

| Model | Top Result | Score | Correct? |
|-------|------------|-------|----------|
| **OpenAI** | `cli.py:51` (argument parsing) | 0.43 | ✅ Yes |
| **Nomic** | `commands/_common.py:81` (argument helpers) | 0.57 | ⚠️ Partial |
| **BGE** | `cli.py:241` (main CLI parser) | 0.71 | ✅ Yes |
| **MiniLM** | `commands/_common.py:1` (shared utilities) | 0.48 | ⚠️ Partial |

**Winner: OpenAI & BGE** - Found the main CLI file.

#### Query 4: "database schema for storing chunks"

| Model | Top Result | Score | Correct? |
|-------|------------|-------|----------|
| **OpenAI** | `indexer.py:451` (chunk insertion) | 0.49 | ⚠️ Partial |
| **Nomic** | `db.py:1` (database module) | 0.70 | ✅ Yes |
| **BGE** | `commands/clean.py:1` (clean command) | 0.61 | ❌ No |
| **MiniLM** | `db.py:21` (SCHEMA definition) | 0.57 | ✅ Yes |

**Winner: Nomic & MiniLM** - Found the database schema.

### Summary

| Metric | OpenAI | Nomic | BGE | MiniLM |
|--------|--------|-------|-----|--------|
| Correct top results | 3/4 | 3/4 | 2/4 | 3/4 |
| Average score | 0.51 | 0.67 | 0.69 | 0.51 |
| Best for conceptual queries | ✅ | ✅ | | |
| Best for keyword-like queries | | | ✅ | |
| Best accuracy/size ratio | | | | ✅ |

### Key Insights

1. **OpenAI and Nomic** excel at conceptual queries requiring understanding of code purpose
2. **BGE** produces higher similarity scores but often misses the most relevant result
3. **MiniLM** matches OpenAI's accuracy despite being 60x smaller and free
4. **All local models** are viable alternatives to OpenAI for semantic code search

---

## Recommendations

### Choosing a Model

| Priority | Model | Alias | When to Use |
|----------|-------|-------|-------------|
| **Speed + Size** | all-MiniLM-L6-v2 | `minilm` | Limited resources, fast iteration, 96% accuracy |
| **Conceptual** | nomic-embed-text-v1.5 | `nomic` | Broad context queries, conceptual understanding |
| **Fallback** | bge-base-en-v1.5 | `bge` | If others don't work well for your codebase |

### For Most Codebases

1. **Try minilm first** - Smallest, fastest, best tested accuracy (96%)
2. **Use 30-line chunks** for minilm/bge, **90-line chunks** for nomic
3. **Always run `ogrep tune`** when changing models or for new codebases

### Configuration

Create a `.env` file in your project root:

```bash
# .env
OGREP_BASE_URL=http://localhost:1234/v1
OGREP_MODEL=nomic-embed-text-v1.5
```

Or set environment variables:

```bash
export OGREP_BASE_URL=http://localhost:1234/v1
export OGREP_MODEL=nomic
```

### Quick Start Commands

```bash
# 1. Start LM Studio server (if not running)
lms server start

# 2. Load model
lms load nomic-ai/nomic-embed-text-v1.5-GGUF -y

# 3. Configure ogrep
export OGREP_BASE_URL=http://localhost:1234/v1

# 4. Index with optimal settings
ogrep index . -m nomic --chunk-lines 90

# 5. Query
ogrep query "your search query" -m nomic
```

---

## Troubleshooting

### "command not found: lms"

The CLI isn't in your PATH. Find and bootstrap it:

```bash
# Check where LM Studio home is
cat ~/.lmstudio-home-pointer

# Bootstrap from that location
$(cat ~/.lmstudio-home-pointer)/bin/lms bootstrap

# Reload shell
source ~/.bashrc
```

### "ENOENT: spawn lm-studio" error

LM Studio GUI isn't running. The CLI communicates with the GUI process.

```bash
# Start LM Studio (GUI or headless)
# On Linux, run the AppImage:
~/path/to/LM-Studio-*.AppImage &
```

### "Dimension mismatch" error

You're querying with a different model than what was used for indexing.

```
Dimension mismatch: query uses 768D (nomic) but index was built with 1536D (small).
```

**Fix:** Either:
- Query with the same model: `ogrep query "..." -m small`
- Or reindex with the new model: `ogrep reindex . -m nomic`

### Low accuracy / poor results

1. **Wrong chunk size for your model** - Run `ogrep tune . -m <model>` to find optimal
2. **Model not loaded** - Check `lms status` and load the correct model
3. **Stale index** - Use `--refresh` flag or reindex: `ogrep reindex .`

### Server not responding

```bash
# Check server status
lms server status

# Restart if needed
lms server stop
lms server start --port 1234
```

---

## Appendix: Raw Test Data

### Environment

- **OS:** Ubuntu 22.04 (Linux 5.15.0)
- **LM Studio:** 0.3.x
- **ogrep:** 0.3.4
- **Test codebase:** ogrep repository (29 source files)

### Nomic Indexing Stats

```
Files: 29 indexed, 0 skipped
Chunks: 52 (at 90-line chunks)
Model: nomic-embed-text-v1.5
Dimensions: 768
DB Size: 316 KB
Index Time: ~16 seconds
```

### BGE Indexing Stats

```
Files: 29 indexed, 0 skipped
Chunks: 52 (at 90-line chunks)
Model: bge-base-en-v1.5
Dimensions: 768
DB Size: 316 KB
Index Time: ~9 seconds (faster due to Q8 quantization)
```

### Test Patterns Used by `ogrep tune`

```
ogrep/commands/reindex.py:17 -> "where is the function cmd_reindex defined..."
ogrep/cli.py:65 -> "where is the function _build_parser defined..."
tests/conftest.py:14 -> "where is the function temp_dir defined..."
ogrep/search.py:63 -> "where is the function query defined..."
ogrep/commands/_common.py:82 -> "where is the function add_scope_args defined..."
```

---

## Contributing

Found different results with other models or codebases? Please share your findings by opening an issue or PR with your tuning data.

Models to test:
- [ ] `all-MiniLM-L6-v2` (smaller, faster)
- [ ] `e5-base-v2` (Microsoft's embedding model)
- [ ] `instructor-base` (instruction-tuned embeddings)
- [ ] `gte-base` (Alibaba's general text embeddings)
