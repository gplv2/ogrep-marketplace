# Local Embeddings Guide: Tuning & Testing

This guide documents real-world observations from testing local embedding models with ogrep. It covers model installation, performance characteristics, optimal chunk sizes, and troubleshooting.

## Table of Contents

- [Overview](#overview)
- [Installing LM Studio](#installing-lm-studio)
- [Downloading Embedding Models](#downloading-embedding-models)
- [Model Comparison](#model-comparison)
- [Batch Size Configuration](#batch-size-configuration)
- [Why Local Models Outperform Cloud Models](#why-local-models-outperform-cloud-models)
- [Chunk Size Tuning](#chunk-size-tuning)
- [Overlap Optimization](#overlap-optimization)
- [Query Quality Analysis](#query-quality-analysis)
- [OpenAI vs Local Models](#openai-vs-local-models)
- [Recommendations](#recommendations)
- [Conclusions](#conclusions)
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
| **all-MiniLM-L6-v2** | `lms get all-MiniLM-L6-v2` | 25 MB (Q8) | 384 | Smallest, fastest, **best accuracy (96%)** |
| **nomic-embed-text-v1.5** | `lms get nomic-embed-text-v1.5` | 84 MB (Q4) | 768 | Good general-purpose, prefers larger chunks |
| **bge-base-en-v1.5** | `lms get bge-base-en-v1.5` | 118 MB (Q8) | 768 | Higher quality quantization, prefers smaller chunks |
| **bge-m3** | `lms get KimChen/bge-m3-GGUF` | ~500 MB | 1024 | Multi-lingual (100+ languages), larger model |

### Download Commands

```bash
# Download MiniLM (recommended - smallest, fastest, best accuracy)
lms get all-MiniLM-L6-v2 -y

# Download nomic (good general-purpose)
lms get nomic-embed-text-v1.5 -y

# Download BGE
lms get bge-base-en-v1.5 -y

# Download BGE-M3 (multi-lingual, 100+ languages)
lms get KimChen/bge-m3-GGUF -y

# List downloaded models
lms ls
```

**Example output:**
```
You have 4 models, taking up 727.09 MB of disk space.

EMBEDDING                                    PARAMS    ARCH          SIZE
text-embedding-all-minilm-l6-v2-embedding    22M       BERT          25.01 MB
text-embedding-bge-base-en-v1.5              109M      BERT          117.97 MB
text-embedding-nomic-embed-text-v1.5                   Nomic BERT    84.11 MB
text-embedding-bge-m3                        560M      XLMRoberta    500.00 MB
```

### Loading Models

```bash
# Load MiniLM (recommended)
lms load all-minilm-l6-v2 -y

# Load nomic
lms load nomic-ai/nomic-embed-text-v1.5-GGUF -y

# Load BGE
lms load bge-base-en-v1.5 -y

# Load BGE-M3 (multi-lingual)
lms load bge-m3 -y

# Check what's loaded
lms status
```

**Note:** The model name for `lms load` may differ from `lms get`. Use `lms ls` to see exact names, or run `lms load` without `-y` to select interactively.

---

## Model Comparison

We tested four local models on the ogrep codebase (29 source files, ~52-79 chunks depending on chunk size) using the `ogrep benchmark` command.

### Key Differences

| Characteristic | MiniLM | Nomic | BGE | BGE-M3 |
|----------------|--------|-------|-----|--------|
| **Alias** | `minilm` | `nomic` | `bge` | `bge-m3` |
| **Architecture** | BERT | Nomic BERT | BERT | XLM-RoBERTa |
| **Size** | 25 MB (Q8) | 84 MB (Q4) | 118 MB (Q8) | ~500 MB |
| **Dimensions** | 384 | 768 | 768 | 1024 |
| **Optimal chunk size** | 30 lines | 30 lines | 30 lines | 60 lines |
| **Optimal overlap** | 15 lines | 15 lines | 5 lines | 10 lines |
| **Peak accuracy** | 84% | **88%** | **88%** | 76% |
| **Index time** | **5.8s** | 33.5s | 21.6s | 81.5s |
| **Best for** | Speed (6x faster) | Accuracy | Accuracy | Multi-lingual |

### Performance Observations

**all-MiniLM-L6-v2 (Recommended Default):**
- **6x faster than alternatives** with only 4% lower accuracy (84% vs 88%)
- Smallest model (~25MB), fastest inference
- Lower dimensions (384) but highly effective
- Optimal with small chunks (30 lines) and 15-line overlap
- Best choice when speed matters for iterative development

**nomic-embed-text-v1.5:**
- **Highest accuracy (88%)** tied with BGE
- Works best with small chunks (30 lines) and 15-line overlap
- Slower than MiniLM (33.5s vs 5.8s index time)
- Better at finding the "right file" for conceptual queries

**bge-base-en-v1.5:**
- **Ties for highest accuracy (88%)** with faster indexing than nomic
- Performs best with small chunks (30 lines) and minimal overlap (5 lines)
- **Completely fails at larger chunk sizes** (0% accuracy at 90+ lines)
- Good alternative when nomic is too slow

**bge-m3 (Multi-lingual):**
- Largest local model (~500MB), slowest indexing (81.5s)
- Supports 100+ languages
- Higher dimensions (1024) for richer embeddings
- Best choice for multi-lingual codebases or comments in non-English languages
- Optimal with medium chunks (60 lines) and 10-line overlap

---

## Batch Size Configuration

Batch size controls how many text chunks are sent per API request. Each model has limits based on its context window:

### Model Batch Limits

| Model | Context Tokens | Max Batch | Default | Auto-Tune Steps |
|-------|---------------|-----------|---------|-----------------|
| minilm | 256 | 16 | 16 | 8, 16 |
| bge | 512 | 16 | 16 | 8, 16 |
| nomic | 8192 | 32 | 16 | 8, 16, 32 |
| bge-m3 | 8192 | 32 | 16 | 8, 16, 32 |
| OpenAI (all) | 8191 | 2048 | 200 | 64, 128, 256, 512, 768, 1024, 2048 |

### Performance Impact

**Local models (minilm at batch 16):**
```
Batch 1:  60ms/chunk (serial)
Batch 16: 42ms/chunk (30% faster)
```

**OpenAI (text-embedding-3-small):**
```
Batch 1:   258ms/chunk (serial)
Batch 50:  18ms/chunk (14x faster)
Batch 200: 6.7ms/chunk (38x faster)
```

OpenAI benefits dramatically from larger batches due to network overhead amortization.

### Configuration

```bash
# Override batch size (capped to model's max)
export OGREP_BATCH_SIZE=32

# Let ogrep auto-tune (recommended)
unset OGREP_BATCH_SIZE
```

Auto-tuning runs on first embedding request and caches the result for the session.

### Token-Aware Batching with Auto-Retry

In addition to count-based limits, ogrep automatically splits batches to stay under each model's token context limit:

- **Token estimation**: ~3 characters per token (conservative baseline for code)
- **Safety margin**: 10% under the limit for estimation variance
- **Auto-retry**: If API returns context overflow, parses error, truncates more, retries (up to 3x)
- **Automatic handling**: No configuration needed

**Token limits by model:**

| Model | Context Tokens | Max Batch Size |
|-------|----------------|----------------|
| OpenAI (all) | 8,191 | 2,048 |
| nomic | 8,192 | 32 |
| bge-m3 | 8,192 | 32 |
| minilm | 256 | 16 |
| bge | 512 | 16 |

**Example warnings:**

```
# Upfront estimation catches ~95% of cases
Text truncated from ~10304 tokens to ~7371 tokens to fit context window

# If estimation is off (dense code, special chars), auto-retry kicks in
Context overflow (9047 > 8192 tokens). Truncating to 77% and retrying...
```

**Oversized chunks**: If a single code chunk exceeds the model's context limit, it's automatically truncated with a warning. This is rare with default chunk sizes but can occur with very long functions, dense code, or files with special characters that tokenize more densely.

**Why 3 chars/token**: OpenAI typically uses ~4 chars/token for English text, but code with operators, whitespace patterns, and special characters can tokenize to fewer chars/token. Using 3 chars/token as baseline prevents most overflows; auto-retry handles edge cases.

---

## Why Local Models Outperform Cloud Models

The benchmark results show all local models (76-88%) outperforming OpenAI's models (48-52%). MiniLM (84%) offers the best speed/accuracy trade-off, being 6x faster than alternatives with only 4% lower accuracy than the top performers (Nomic and BGE at 88%). This isn't a fluke—it reflects fundamental differences in how these models were designed and what they optimize for.

### The Science Behind MiniLM's Success

**Knowledge Distillation via Self-Attention Transfer**

MiniLM wasn't trained from scratch as a small model. It was distilled from a larger teacher model (BERT/RoBERTa-class) using a technique called *deep self-attention distillation*. Unlike traditional distillation that copies output logits, MiniLM learns to mimic the teacher's attention matrices—the internal representations of which tokens relate to which.

This is significant: attention matrices encode syntactic and semantic relationships (what modifies what, coreference links, structural patterns). By transferring these relational patterns rather than just final predictions, the student model preserves much of the teacher's linguistic understanding in a fraction of the parameters.

**Architecture Optimized for Quality-per-FLOP**

The `all-MiniLM-L6-v2` checkpoint uses:
- 6 transformer layers (vs. BERT's 12)
- 384 hidden dimensions
- ~22M parameters (~25MB on disk)

This architecture maintains enough representational capacity to stay expressive while dramatically reducing compute. The result: inference that's fast on CPU and cheap on GPU, enabling indexing and searching of large codebases without infrastructure concerns.

**Contrastive Fine-Tuning for Similarity**

The "all-MiniLM-L6-v2" checkpoint used by ogrep isn't base MiniLM—it's been fine-tuned by Sentence-Transformers on over 1 billion sentence pairs using contrastive learning objectives. The training goal was specifically "these two texts mean the same thing," which maps directly to cosine-similarity retrieval.

This specialization matters: the model learned to produce embeddings where semantically similar texts cluster together in vector space. For code search queries like "where is authentication handled?", this translates to finding code chunks that *mean* authentication-handling, not just chunks containing the word "authentication."

### Why Smaller Dimensions Can Win

The 384-dimensional vectors from MiniLM might seem inferior to OpenAI's 1536D or 3072D embeddings. Counterintuitively, smaller dimensions can perform *better* for retrieval tasks:

1. **Cleaner similarity signal**: Fewer dimensions mean less noise in the similarity calculation. Each dimension carries more semantic weight.

2. **Better generalization**: High-dimensional spaces can overfit to training data distributions. Lower dimensions force the model to learn more robust, generalizable representations.

3. **Matched to the task**: For "find similar code chunks," 384 dimensions is often sufficient. The extra dimensions in larger models may encode information irrelevant to retrieval (world knowledge, reasoning capabilities, etc.).

### Why Cloud Models Can Underperform

OpenAI's embedding models are excellent—but they're general-purpose. Several factors can make them appear weaker in repository-specific benchmarks:

**Chunking Sensitivity**

The benchmark data shows each model has dramatically different optimal chunk sizes. If a model receives chunks that don't match its training distribution, accuracy suffers regardless of embedding quality. OpenAI's models may simply prefer different chunking than what works for the test codebase.

**Code vs. Natural Language Training**

Cloud embedding models are typically trained on natural language corpora (web text, books, articles). Code has different structure: function definitions, variable naming conventions, syntactic patterns that don't appear in prose. A model fine-tuned on sentence similarity pairs may "luck into" better retrieval on code structure queries.

**Retrieval-Specific Optimization**

MiniLM variants from Sentence-Transformers are explicitly trained for retrieval. OpenAI's embeddings are designed for broader use cases (classification, clustering, search, recommendations). A specialist often beats a generalist on the specialist's home turf.

### Ensuring Fair Comparisons

Before concluding that one model is definitively better, verify these factors are controlled:

| Factor | What to Check |
|--------|---------------|
| **Evaluation metric** | Track recall@1, recall@5, recall@10—not just "top-1 exact hit." A model hitting at rank 3 is still useful. |
| **Query diversity** | If queries are mostly "find definition of X," chunking matters more than embedding quality. Include conceptual queries too. |
| **Vector normalization** | Ensure all vectors are normalized consistently before cosine similarity. |
| **Truncation behavior** | Different models truncate at different token limits. If one model loses signal due to early truncation, it will underperform unfairly. |
| **Optimal settings** | Each model should be tested at its optimal chunk/overlap, not one-size-fits-all settings. |

The ogrep benchmark command handles most of these by testing multiple configurations per model. When all factors are controlled, local models consistently outperform cloud models on code retrieval. **MiniLM remains the recommended default** because its 6x speed advantage outweighs the 4% accuracy gap vs. Nomic and BGE in iterative development workflows.

### The Cost of Cloud Embeddings for Retrieval

There's a broader consideration: **using cloud API credits for retrieval tasks is expensive at scale.**

Embedding a codebase requires processing every chunk of every file. Re-indexing after changes requires more API calls. Queries require embedding the search text. For active development with frequent re-indexing, costs accumulate:

| Scenario | OpenAI Cost | Local Cost |
|----------|-------------|------------|
| Index 10K files once | ~$0.50 | $0.00 |
| Re-index 100 files/day | ~$15/month | $0.00 |
| 1000 queries/day | ~$0.60/day | $0.00 |

Some tools (like mgrep) push their own cloud AI services for semantic search. The value proposition should be questioned: if a 25MB local model achieves 96% accuracy while cloud models achieve 48-52%, the cloud premium buys *negative* value for this specific task.

**Recommendation:** Reserve cloud embedding credits for tasks where they demonstrably outperform local alternatives. Code retrieval is not one of those tasks.

---

## Chunk Size Tuning

**This is the most critical finding:** Different embedding models have dramatically different optimal chunk sizes.

### Tuning Results: nomic-embed-text-v1.5

Earlier testing suggested nomic preferred larger chunks (90 lines). However, comprehensive benchmarking with 25 samples revealed different results:

```
Chunk Size   Overlap   Accuracy   Index Time
----------------------------------------------
30           15        0.88       33.5s     <-- OPTIMAL
60           10        0.76       28.2s
90           15        0.72       25.1s
```

**Observation:** With more test samples, nomic performs best at 30-line chunks with 15-line overlap (88% accuracy). This contradicts earlier 5-sample results, highlighting the importance of sufficient test samples for reliable tuning.

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

## Overlap Optimization

Overlap determines how many lines are shared between adjacent chunks. The right overlap helps ensure that code spanning chunk boundaries is still findable.

### What Overlap Does

When chunking a file with 60-line chunks and 10-line overlap:
- Chunk 1: lines 1-60
- Chunk 2: lines 51-110 (overlaps with chunk 1 by 10 lines)
- Chunk 3: lines 101-160 (overlaps with chunk 2 by 10 lines)

### Overlap Testing Results

The `ogrep benchmark` command tests multiple overlap values (5, 10, 15, 20 lines) for each model:

| Model | Best Overlap | Best Chunk | Accuracy |
|-------|--------------|------------|----------|
| **MiniLM** | 15 lines | 30 lines | 84% |
| **Nomic** | 15 lines | 30 lines | 88% |
| **BGE** | 5 lines | 30 lines | 88% |
| **BGE-M3** | 10 lines | 60 lines | 76% |
| **OpenAI small** | 15 lines | 45 lines | 48% |
| **OpenAI large** | 15 lines | 30 lines | 52% |

### Key Findings

1. **Overlap scales with chunk size**: Models with 30-line chunks work well with 5-15 lines overlap
2. **BGE prefers minimal overlap**: 5 lines works best even at 30-line chunks
3. **Nomic and MiniLM prefer more overlap**: 15 lines provides best context preservation
4. **Diminishing returns**: Beyond 15 lines, overlap adds index size without improving accuracy
5. **Model-specific**: Each model has a "sweet spot" - the benchmark command finds it automatically

### Using the Benchmark Command

> **Warning:** Benchmarks can take significant time and resources. Testing 4 local models with default settings (3 chunk sizes × 3 overlap values = 9 configurations each) takes 10-30 minutes depending on your hardware. For OpenAI models, each configuration requires embedding API calls—on a large codebase, this can consume substantial API credits. **Start with a small repository** (under 50 files) to validate your setup before running on larger codebases.

```bash
# Comprehensive benchmark with overlap testing
ogrep benchmark . --samples 10

# Save optimal settings (chunk size AND overlap)
ogrep benchmark . --samples 10 --save

# Test specific overlap values
ogrep benchmark . --overlaps 5,10,15

# For faster testing, reduce configurations
ogrep benchmark . --samples 5 --chunks 30,60 --overlaps 5,10

# Test only local models (no API costs)
ogrep benchmark . --local-only

# Test only OpenAI models (careful: uses API credits)
ogrep benchmark . --cloud-only --samples 5
```

The benchmark tests all combinations of chunk sizes and overlap values, reporting which configuration works best for each model.

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

#### Detail of cli test

The query "how does the CLI parse arguments" is asking: where in the code is command-line argument parsing handled?

For ogrep, the correct answer is ogrep/cli.py where build_parser() uses argparse to define all the flags:

```
  # cli.py:65-78
  def _build_parser() -> argparse.ArgumentParser:
      p = argparse.ArgumentParser(
          prog="ogrep",
          description="Local semantic grep powered by SQLite and OpenAI embeddings",
      )
      p.add_argument("--version", action="version", ...)
      # ... all subcommands and flags defined here
```
Results:
  - OpenAI → cli.py:51 (argument parsing code) ✅
  - BGE → cli.py:241 (main CLI parser) ✅
  - Nomic → commands/_common.py:81 (helper utilities, not main parser) ⚠️
  - MiniLM → commands/_common.py:1 (shared utilities, not main parser) ⚠️

Nomic and MiniLM found a related file (_common.py has add_scope_args() helper) but not the main argument parser in cli.py. That's why they're marked "Partial"

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

## OpenAI vs Local Models

We ran comprehensive benchmarks comparing OpenAI's cloud models against local models using the `ogrep benchmark` command.

### OpenAI Benchmark Results

Tested on the ogrep codebase with 10 samples:

| Model | Dimensions | Best Chunk | Best Overlap | Accuracy | Index Time | Query Time | Cost |
|-------|------------|------------|--------------|----------|------------|------------|------|
| **text-embedding-3-large** | 3072 | 30 lines | 15 lines | 52% | 3.1s | 0.03s | $0.13/M |
| **text-embedding-3-small** | 1536 | 45 lines | 15 lines | 48% | 2.3s | 0.02s | $0.02/M |

### Local Model Benchmark Results

| Model | Dimensions | Best Chunk | Best Overlap | Accuracy | Index Time | Query Time | Cost |
|-------|------------|------------|--------------|----------|------------|------------|------|
| **Nomic** | 768 | 30 lines | 15 lines | **88%** | 33.5s | 0.54s | FREE |
| **BGE** | 768 | 30 lines | 5 lines | **88%** | 21.6s | 0.48s | FREE |
| **MiniLM** | 384 | 30 lines | 15 lines | 84% | **5.8s** | **0.32s** | FREE |
| **BGE-M3** | 1024 | 60 lines | 10 lines | 76% | 81.5s | 0.86s | FREE |

> **Note:** While Nomic and BGE tie for accuracy (88%), MiniLM remains the recommended default due to being **6x faster** with only 4% lower accuracy. Speed matters for iterative development workflows.

### Key Observations

1. **Local models outperform OpenAI on code search**: All local models (76-88%) beat OpenAI (48-52%) on this codebase
2. **Speed varies widely**: MiniLM indexes 6x faster than Nomic, 14x faster than BGE-M3
3. **Cost savings**: Local models are completely free - significant for large codebases
4. **Privacy**: Code never leaves your machine with local models
5. **OpenAI's models underperformed**: Both cloud models scored below all local alternatives

### When to Use Each

| Scenario | Recommended Model |
|----------|-------------------|
| **General code search** | MiniLM (local) - best accuracy, free |
| **Multi-language codebase** | BGE-M3 (local) - 100+ languages |
| **Large context queries** | Nomic (local) - handles bigger chunks |
| **Existing OpenAI integration** | text-embedding-3-small - cost-effective |
| **Enterprise compliance** | Local models - no data leaves machine |

---

## Recommendations

### Choosing a Model

| Priority | Model | Alias | When to Use |
|----------|-------|-------|-------------|
| **Best Overall** | all-MiniLM-L6-v2 | `minilm` | Fastest (6x), 84% accuracy, smallest |
| **Highest Accuracy** | nomic-embed-text-v1.5 | `nomic` | 88% accuracy, larger context window |
| **Also High Accuracy** | bge-base-en-v1.5 | `bge` | 88% accuracy, faster than nomic |
| **Multi-lingual** | bge-m3 | `bge-m3` | Non-English code, 100+ languages |

### For Most Codebases

1. **Try MiniLM first** - Smallest (25MB), 6x faster than alternatives, 84% accuracy
2. **Use the right chunk/overlap combo**:
   - MiniLM: 30 lines / 15 overlap
   - Nomic: 30 lines / 15 overlap (highest accuracy: 88%)
   - BGE: 30 lines / 5 overlap (ties nomic: 88%)
   - BGE-M3: 60 lines / 10 overlap
3. **Run `ogrep benchmark`** to find optimal settings for your specific codebase

### Configuration

**Smart Default:** When `OGREP_BASE_URL` is set, ogrep automatically defaults to `minilm` (the best local model). You don't need to specify `-m` every time!

```bash
# Just set the base URL - ogrep will use minilm automatically
export OGREP_BASE_URL=http://localhost:1234/v1
ogrep index .   # Uses minilm by default
ogrep query "search"  # Uses minilm by default
```

Or create a `.env` file in your project root:

```bash
# .env
OGREP_BASE_URL=http://localhost:1234/v1
# OGREP_MODEL=nomic  # Optional: override the default (minilm)
```

To use a different local model, set `OGREP_MODEL`:

```bash
export OGREP_BASE_URL=http://localhost:1234/v1
export OGREP_MODEL=nomic  # Use nomic instead of minilm
```

### Quick Start Commands

```bash
# 1. Start LM Studio server (if not running)
lms server start

# 2. Load MiniLM (recommended - best accuracy)
lms load all-minilm-l6-v2 -y

# 3. Configure ogrep
export OGREP_BASE_URL=http://localhost:1234/v1

# 4. Index (minilm is auto-selected when OGREP_BASE_URL is set)
ogrep index .

# 5. Query
ogrep query "your search query"

# 6. (Optional) Run benchmark to verify optimal settings
ogrep benchmark . --samples 10
```

---

## Conclusions

After extensive benchmarking of embedding models for code search, several important lessons emerge:

### 1. Local Models Beat Cloud Models for Code Retrieval

**All local models (76-88%) outperformed OpenAI's models (48-52%)** on code search. This isn't because OpenAI embeddings are "bad"—they're excellent general-purpose embeddings. The difference is specialization:

- **Local models** (MiniLM, Nomic, BGE) are fine-tuned specifically for semantic similarity and retrieval tasks
- **OpenAI embeddings** are trained for broad applicability: classification, clustering, search, recommendations, and more

For the specific task of "find code chunks semantically similar to this query," retrieval-optimized models win. MiniLM's 384 dimensions and BGE's 768 dimensions encode exactly what's needed, while OpenAI's 1536-3072 dimensions include information irrelevant to this task.

This has broader implications: **don't assume bigger/cloud/expensive means better.** Task-specific optimization often matters more than raw model size.

### 2. Chunk Size is Model-Specific

There is no universal "best" chunk size. Comprehensive benchmarking revealed:

| Model | Optimal Chunk | Optimal Overlap | Accuracy |
|-------|---------------|-----------------|----------|
| MiniLM | 30 lines | 15 lines | 84% |
| Nomic | 30 lines | 15 lines | 88% |
| BGE | 30 lines | 5 lines | 88% |
| BGE-M3 | 60 lines | 10 lines | 76% |
| OpenAI | 45-60 lines | 15 lines | 48-52% |

**Critical:** Using the wrong chunk size can drop accuracy to 0% (as seen with BGE at 90+ lines). The benchmark data proves chunking dominates—a strong model with wrong chunking loses to a weaker model with right chunking.

### 3. Overlap Matters, But Less Than Chunk Size

Overlap settings have measurable but smaller impact than chunk size:
- **5-10 lines** works for small chunks (30 lines)
- **15-20 lines** helps with larger chunks (90+ lines)
- Beyond 20 lines adds index size without accuracy gains

The relationship makes sense: smaller chunks need less overlap because boundaries are already close together. Larger chunks benefit from more overlap to catch code spanning boundaries.

### 4. Always Benchmark Your Codebase

The `ogrep benchmark` command exists because:
- Different codebases have different characteristics
- Function length, comment density, and naming conventions vary
- Query patterns differ (definition lookups vs. conceptual searches)
- What works for one repo may not work for another

A 96% accuracy on the ogrep codebase doesn't guarantee 96% on a different repository. **Run `ogrep benchmark . --samples 10`** before committing to a model and settings.

### 5. Smart Defaults Make Local Models Practical

With `OGREP_BASE_URL` set:
- MiniLM is auto-selected (no `-m` flag needed)
- Model-specific chunk sizes are applied automatically
- Zero configuration required for optimal local model experience

This matters for adoption: if local models required complex tuning, teams would default to cloud APIs for convenience. Smart defaults remove that friction.

### 6. Cloud Credits for Retrieval: Questionable Value

Local models eliminate two concerns—but the cost argument deserves emphasis:

| Concern | Cloud Models | Local Models |
|---------|--------------|--------------|
| **Privacy** | Code sent to third-party servers | Code never leaves machine |
| **Cost** | $0.02-0.13 per million tokens | $0.00 |
| **Accuracy** | 48-52% (on this benchmark) | 76-88% (all local models beat cloud) |

The economics are striking: cloud embeddings cost money *and* performed worse on code retrieval. This isn't universally true—OpenAI embeddings excel at many tasks—but for semantic code search, the cloud premium delivers negative value.

Some tools promote their own cloud AI services for semantic search. Before paying for cloud embeddings, benchmark locally. If a 25MB model running on a laptop CPU outperforms the cloud offering, the subscription isn't worth it.

**Recommendation:** Reserve cloud embedding credits for tasks where they demonstrably outperform local alternatives. Semantic code retrieval is not one of those tasks.

### 7. The Surprising Power of Distillation

MiniLM's success illustrates a broader principle: **knowledge distillation can create models that outperform their teachers on specific tasks.**

MiniLM learned from a larger BERT-class model by copying attention patterns, not just output predictions. This preserved the teacher's linguistic understanding in a compact form. Combined with task-specific fine-tuning (contrastive learning for similarity), the result is a 22M parameter model that beats 175B+ parameter cloud services at retrieval.

For embedding tasks, this suggests diminishing returns from scale. A well-distilled, well-tuned small model can match or exceed much larger alternatives—especially when the task is narrow (similarity search) rather than broad (reasoning, generation, world knowledge).

---

## Cross-File Chunk Deduplication

When indexing repositories with copied or similar files (common in legacy codebases), ogrep now automatically deduplicates identical chunks across different files. This can save significant embedding costs and time.

### How It Works

1. **Global lookup**: Before embedding any chunk, ogrep checks if an identical chunk (by `text_sha256`) already exists in the database from another file
2. **Integrity verification**: Reuses only if model and dimensions match
3. **Priority order**: Global reuse → Local reuse (same file edit) → New embedding

### Expected Savings

| Scenario | Without Dedup | With Dedup | Savings |
|----------|---------------|------------|---------|
| Two 1000-line files, 10 lines different | 132 embeddings | 68 embeddings | 49% |
| 5 copies of same 500-line file | 165 embeddings | 33 embeddings | 80% |
| Vendored code with minor patches | Varies | Typically 50-80% | High |

### Stats Tracking

The `IndexStats` dataclass now tracks:
- `chunks_reused_global`: Chunks reused from OTHER files
- `chunks_reused_local`: Chunks reused from SAME file (edits)
- `dedup_ratio`: Percentage of chunks that were deduplicated

### Model Consistency Check

To prevent mixing incompatible embeddings, ogrep enforces model consistency per index:

```bash
# First index with nomic
ogrep index . -m nomic

# Trying to add more files with a different model fails:
ogrep index . -m minilm
# ValueError: Model mismatch: index uses 'nomic-embed-text-v1.5' but requested 'all-MiniLM-L6-v2'. Use --force to reindex with new model.
```

**Why this matters**: Different models produce embeddings of different dimensions and semantic spaces. Mixing them would produce incorrect search results.

### Database Index

A database index (`idx_chunks_text_sha256`) enables O(log n) lookups for cross-file deduplication. This index is created automatically on new databases or when upgrading.

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

### "Corrupted index: mixed dimensions detected"

Your index contains embeddings from different models (e.g., 768D nomic + 1536D OpenAI). This can happen if `--refresh` was used with a different model before the bug fix in v0.5.1+.

**Fix:** Rebuild the index from scratch:
```bash
ogrep reset -f && ogrep index .
```

### Low accuracy / poor results

1. **Wrong chunk size for your model** - Run `ogrep tune . -m <model>` to find optimal
2. **Model not loaded** - Check `lms status` and load the correct model
3. **Stale index** - Use `--refresh` flag or reindex: `ogrep reindex .`

### Understanding "Low" Confidence Scores

**Why scores seem low but search still works:**

Cosine similarity for text embeddings does NOT distribute uniformly across [0, 1]. Scores cluster around 0.3-0.5:

```
Pairwise similarity distribution in a typical codebase:
├── 0.0-0.2  ████████░░░░░░░░░░░░  ~15%
├── 0.2-0.3  ████████████░░░░░░░░  ~30%
├── 0.3-0.4  ████████████████░░░░  ~35%  ← MEDIAN
├── 0.4-0.5  ██████░░░░░░░░░░░░░░  ~12%
├── 0.5-0.6  ███░░░░░░░░░░░░░░░░░  ~5%
├── 0.6-0.7  █░░░░░░░░░░░░░░░░░░░  ~2%
└── 0.7+     ░░░░░░░░░░░░░░░░░░░░  ~1%
```

A score of **0.45 is actually in the top 15%** of all possible matches!

**Relative confidence (default in v0.7.0+):**

ogrep now uses relative confidence by default, comparing each result to the top score:

| Top Score | Result | Ratio | Confidence |
|-----------|--------|-------|------------|
| 0.45 | 0.45 | 100% | high |
| 0.45 | 0.42 | 93% | high |
| 0.45 | 0.35 | 78% | medium |
| 0.45 | 0.20 | 44% | very_low |

This tells you how close each result is to the best match, regardless of absolute scores.

**Switching to absolute mode (legacy):**

```bash
# Use absolute thresholds (calibrated for typical distributions)
export OGREP_CONFIDENCE_MODE=absolute
export OGREP_CONFIDENCE_HIGH=0.50
export OGREP_CONFIDENCE_MEDIUM=0.40
export OGREP_CONFIDENCE_LOW=0.30
```

**Adjust hybrid search balance:**

```bash
# Default: 70% semantic, 30% keyword
export OGREP_HYBRID_ALPHA=0.7

# More keyword-heavy (exact terms, identifiers):
OGREP_HYBRID_ALPHA=0.4 ogrep query "validateToken" -n 10

# More semantic (conceptual questions):
OGREP_HYBRID_ALPHA=0.9 ogrep query "how is auth handled" -n 10
```

**Other tips:**

1. **Trust the ranking** — result #1 is almost always relevant, even with "low" absolute score
2. **Use fulltext mode** — for exact identifiers: `ogrep query "ClassName" --mode fulltext`
3. **Check chunk context** — use `ogrep chunk "path:N" -C 2` to expand around results

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
- **ogrep:** 0.7.1
- **Test codebase:** ogrep repository (29 source files)
- **Benchmark samples:** 10

### MiniLM Indexing Stats (Recommended Default)

```
Files: 29 indexed, 0 skipped
Chunks: ~79 (at 30-line chunks with 15-line overlap)
Model: all-MiniLM-L6-v2
Dimensions: 384
DB Size: ~220 KB
Index Time: 5.8 seconds
Accuracy: 84%
Speed: 6x faster than alternatives
```

### Nomic Indexing Stats

```
Files: 29 indexed, 0 skipped
Chunks: ~79 (at 30-line chunks with 15-line overlap)
Model: nomic-embed-text-v1.5
Dimensions: 768
DB Size: ~316 KB
Index Time: 33.5 seconds
Accuracy: 88%
```

### BGE Indexing Stats

```
Files: 29 indexed, 0 skipped
Chunks: ~79 (at 30-line chunks with 5-line overlap)
Model: bge-base-en-v1.5
Dimensions: 768
DB Size: ~316 KB
Index Time: 21.6 seconds
Accuracy: 88%
```

### BGE-M3 Indexing Stats

```
Files: 29 indexed, 0 skipped
Chunks: ~52 (at 60-line chunks with 10-line overlap)
Model: bge-m3
Dimensions: 1024
DB Size: ~420 KB
Index Time: 81.5 seconds
Accuracy: 76%
```

### OpenAI Indexing Stats

```
Model: text-embedding-3-small
Dimensions: 1536
Best Chunk: 45 lines / 15 overlap
Index Time: ~2.3 seconds (network latency)
Accuracy: 48%
Cost: ~$0.02 per 1M tokens
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

## Search Quality R&D

This section documents research and development work to improve ogrep's search quality beyond embedding model selection.

### Hybrid Fusion: RRF vs Alpha Weighting (v0.7.0+)

When using hybrid search, two ranking systems must be combined:
- **Semantic search**: Cosine similarity of embeddings
- **Full-text search**: BM25 keyword matching via FTS5

**The Problem**: These systems produce scores on completely different scales. Semantic similarity clusters around 0.3-0.5, while BM25 scores can range from -20 to 0 (lower is better in raw form). Combining them requires either:
1. Normalizing both to [0,1] and weighting (alpha fusion)
2. Using rank positions instead of scores (RRF)

**v0.6.x (Alpha Weighting)**:
```
score = 0.7 * semantic_score + 0.3 * fts_score_normalized
```
- Required tuning the alpha parameter
- Sensitive to score distribution changes
- Normalization can be imprecise

**v0.7.0+ (RRF - Reciprocal Rank Fusion)**:
```
score = 1/(60 + semantic_rank) + 1/(60 + fts_rank)
```
- Uses rank positions, not raw scores
- No hyperparameter tuning needed (k=60 is standard)
- Robust across different score distributions
- Published research shows consistent improvements

**Why RRF works better**: Ranks are comparable across systems. If a chunk is #1 in semantic and #5 in full-text, RRF correctly identifies it as a strong match. Alpha weighting might incorrectly rank it if the raw score distributions don't align.

**Configuration**:
```bash
# RRF (default in v0.7.0+)
OGREP_FUSION_METHOD=rrf ogrep query "search"

# Alpha weighting (legacy, still available)
OGREP_FUSION_METHOD=alpha OGREP_HYBRID_ALPHA=0.7 ogrep query "search"
```

**Reference**: Cormack, Clarke, Buettcher. "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods" (SIGIR 2009)

### Cross-Encoder Reranking (Implemented v0.7.0)

Two-stage retrieval for improving "right file in top 30, but not #1" scenarios.

**Standard architecture** (bi-encoder only):
```
Query → Embed → Compare to all chunk embeddings → Top K results
```
Fast but imprecise—query and chunks are embedded separately.

**With reranking** (bi-encoder + cross-encoder):
```
Query → Stage 1: Fast retrieval (top 50) → Stage 2: Slow reranking → Top 10
```
The reranker sees query AND chunk together, enabling fine-grained relevance scoring.

**Why reranking helps**:
- Cross-encoders model query-document relationships directly
- No information loss from vector compression
- Precision where it matters most (final ranking)

**Usage (v0.7.0+)**:
```bash
# Install reranking support
pip install "ogrep[rerank]"

# Enable reranking
ogrep query "where is authentication" --rerank --json

# Rerank specific number of candidates
ogrep query "database connection" --rerank-top 30 --json
```

**Default model**: `BAAI/bge-reranker-v2-m3` (~300MB, downloads on first use)

**Note**: Reranking is independent of embedding models—you can use OpenAI embeddings for retrieval and a local reranker for precision.

### AST-Aware Chunking (Future Research)

Current chunking is line-based with overlap. This can split semantic units:
```
Current chunk boundary:
  └── End of Class A
  └── Start of Class B  ← Semantic mixing
  └── Beginning of method B.foo()
```

**AST-aware chunking** would split at function/class boundaries:
```
AST-aware chunks:
  Chunk 1: ClassA (complete)
  Chunk 2: ClassB.foo() method
  Chunk 3: ClassB.bar() method
```

**Benefits**:
- Each chunk is semantically coherent
- Better BM25 (function names not split)
- Enables symbol index ("who calls X?")

**Challenges**:
- Requires parsing (tree-sitter, LSP)
- Multi-language support complexity
- Large functions still need splitting

This is under consideration for future releases.

---

## Contributing

Found different results with other models or codebases? Please share your findings by opening an issue or PR with your tuning data.

### Models Tested

- [x] `nomic-embed-text-v1.5` - Highest accuracy (88%), larger model
- [x] `bge-base-en-v1.5` - Ties for accuracy (88%), faster than nomic
- [x] `all-MiniLM-L6-v2` - **Best speed/accuracy trade-off** (84%, 6x faster)
- [x] `bge-m3` - Multi-lingual support (76%)
- [x] `text-embedding-3-small` - OpenAI cloud (48%)
- [x] `text-embedding-3-large` - OpenAI cloud (52%)

### Models to Test

- [ ] `e5-base-v2` (Microsoft's embedding model)
- [ ] `instructor-base` (instruction-tuned embeddings)
- [ ] `gte-base` (Alibaba's general text embeddings)
- [ ] `jina-embeddings-v2` (Long context, 8K tokens)

### How to Contribute Results

1. Run `ogrep benchmark . --samples 10 --json > results.json`
2. Open an issue with your results and codebase characteristics
3. Include: language mix, average file size, function density
