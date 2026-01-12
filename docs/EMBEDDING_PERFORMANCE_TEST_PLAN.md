# Embedding Performance Test Plan

Created: 2026-01-12
Purpose: Investigate why local embedding performance varies significantly between sessions.

## Background

Previous session showed ~24ms/chunk performance with minilm, but current session shows ~72ms/chunk for the same model. Need to identify root cause after fresh reboot.

## Test Environment

- **Test repo**: `/home/glenn/repos/testsc/opt/strac/`
- **Test file**: `cgpsv85.php` (9232 lines, 330KB PHP)
- **Expected chunks**: ~615 chunks at 30 lines with 15 overlap
- **Avg chunk size**: ~1057 chars (~264 tokens)

## Pre-Test Checklist

```bash
# 1. Verify LM Studio is running
~/.cache/lm-studio/bin/lms server status

# 2. Check loaded models
~/.cache/lm-studio/bin/lms status

# 3. Verify API responds
curl -s http://localhost:1234/v1/models | jq '.data[].id'

# 4. Set environment
export OGREP_BASE_URL=http://localhost:1234/v1
unset OPENAI_API_KEY  # Not needed for local
```

## Test 1: Baseline API Response Time

Test raw API latency without ogrep overhead.

```bash
# Single embedding request
time curl -s http://localhost:1234/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "test string", "model": "text-embedding-all-minilm-l6-v2-embedding"}' \
  > /dev/null

# Expected: <100ms for single short string
```

## Test 2: Serial Mode Baseline (One-by-One)

Test performance when sending requests one at a time (no batching). This establishes the baseline for comparison with batched requests.

```bash
export OGREP_BASE_URL=http://localhost:1234/v1
export OGREP_BATCH_SIZE=1  # Force serial mode

python3 -c "
import time
from ogrep.embed import embed_texts

# Test 16 short strings - serial mode
texts = ['test string ' + str(i) for i in range(16)]
blobs, dim, elapsed = embed_texts(texts, model='minilm', return_timing=True)
print(f'Serial (16 short): {elapsed:.2f}s ({elapsed*1000/16:.1f}ms/chunk)')

# Test 50 short strings - serial mode
texts = ['test string ' + str(i) for i in range(50)]
blobs, dim, elapsed = embed_texts(texts, model='minilm', return_timing=True)
print(f'Serial (50 short): {elapsed:.2f}s ({elapsed*1000/50:.1f}ms/chunk)')
"

unset OGREP_BATCH_SIZE  # Reset for other tests
```

**Expected Results**:
| Test | Target | Acceptable |
|------|--------|------------|
| 16 short (serial) | ~20ms/chunk | <50ms/chunk |
| 50 short (serial) | ~20ms/chunk | <50ms/chunk |

**Why this matters**: If serial mode is significantly faster than batched mode, the batching overhead may be the issue. If both are slow, the problem is with the embedding model/server itself.

## Test 3: Model Comparison (Short Strings)

```bash
export OGREP_BASE_URL=http://localhost:1234/v1
python3 -c "
import time
from ogrep.embed import embed_texts

texts = ['test string ' + str(i) for i in range(16)]

for model in ['minilm', 'nomic']:
    blobs, dim, elapsed = embed_texts(texts, model=model, return_timing=True)
    print(f'{model}: {elapsed:.2f}s ({elapsed*1000/16:.1f}ms/chunk)')
"
```

**Expected Results**:
| Model | Target | Acceptable |
|-------|--------|------------|
| minilm | <25ms/chunk | <50ms/chunk |
| nomic | <50ms/chunk | <150ms/chunk |

## Test 3: Batch Size Auto-Tuning

```bash
export OGREP_BASE_URL=http://localhost:1234/v1
python3 -c "
from ogrep.embed import _find_optimal_batch_size, _create_client
from ogrep.models import resolve_model, resolve_dimensions

texts = ['test ' + str(i) for i in range(100)]
client, is_local = _create_client()
model = resolve_model('minilm')
dims = resolve_dimensions(None, model)

optimal = _find_optimal_batch_size(client, texts, model, dims)
print(f'Optimal batch size: {optimal}')
print(f'is_local: {is_local}')
"
```

**Expected**: Optimal batch size between 32-96, is_local=True

## Test 4: Real PHP Code Embedding

```bash
export OGREP_BASE_URL=http://localhost:1234/v1
python3 -c "
import time
from pathlib import Path
from ogrep.chunking import chunk_lines
from ogrep.embed import embed_texts

php = Path('/home/glenn/repos/testsc/opt/strac/cgpsv85.php').read_text()
chunks = list(chunk_lines(php, chunk_size=30, overlap=15))
texts = [c.text for c in chunks]

print(f'Chunks: {len(texts)}')
print(f'Avg size: {sum(len(t) for t in texts)/len(texts):.0f} chars')

# Test first 100 chunks
blobs, dim, elapsed = embed_texts(texts[:100], model='minilm', return_timing=True)
print(f'100 PHP chunks: {elapsed:.2f}s ({elapsed*1000/100:.1f}ms/chunk)')

# Test all chunks
blobs, dim, elapsed = embed_texts(texts, model='minilm', return_timing=True)
print(f'All {len(texts)} chunks: {elapsed:.2f}s ({elapsed*1000/len(texts):.1f}ms/chunk)')
"
```

**Expected Results**:
| Test | Target | Acceptable |
|------|--------|------------|
| 100 PHP chunks | <50ms/chunk | <100ms/chunk |
| All 615 chunks | <50ms/chunk | <100ms/chunk |

## Test 6: Serial vs Batched Comparison (Real Code)

Direct comparison of serial vs batched mode with real PHP code.

```bash
export OGREP_BASE_URL=http://localhost:1234/v1

python3 -c "
import os
import time
from pathlib import Path
from ogrep.chunking import chunk_lines
from ogrep.embed import embed_texts, _optimal_batch_size

php = Path('/home/glenn/repos/testsc/opt/strac/cgpsv85.php').read_text()
chunks = list(chunk_lines(php, chunk_size=30, overlap=15))
texts = [c.text for c in chunks[:50]]  # Use 50 chunks for comparison

print(f'Testing with {len(texts)} real PHP chunks')
print()

# Test 1: Serial mode (one by one)
os.environ['OGREP_BATCH_SIZE'] = '1'
import ogrep.embed as embed_module
embed_module._optimal_batch_size = None  # Reset cache

blobs, dim, elapsed = embed_texts(texts, model='minilm', return_timing=True)
serial_ms = elapsed * 1000 / len(texts)
print(f'Serial (1 at a time): {elapsed:.2f}s ({serial_ms:.1f}ms/chunk)')

# Test 2: Batched mode (auto-tuned)
del os.environ['OGREP_BATCH_SIZE']
embed_module._optimal_batch_size = None  # Reset cache

blobs, dim, elapsed = embed_texts(texts, model='minilm', return_timing=True)
batched_ms = elapsed * 1000 / len(texts)
print(f'Batched (auto-tuned): {elapsed:.2f}s ({batched_ms:.1f}ms/chunk)')

# Comparison
print()
if serial_ms < batched_ms:
    print(f'Serial is {batched_ms/serial_ms:.1f}x FASTER than batched')
else:
    print(f'Batched is {serial_ms/batched_ms:.1f}x FASTER than serial')
"
```

**Expected Results**:
- Batched should be faster or equal to serial
- If serial is faster, batching overhead is the problem
- If both are slow, the model/server is the bottleneck

## Test 7: Full Index Workflow

```bash
cd /home/glenn/repos/testsc/opt/strac
rm -rf .ogrep
export OGREP_BASE_URL=http://localhost:1234/v1

# Index with minilm
time ogrep index . -m minilm --chunk-lines 30 --overlap 15 -e '*' -i cgpsv85.php

# Check stats
ogrep status
```

**Expected**:
- Total time: <60s (was 114s in slow session)
- Files indexed: 1-2 (symlink may count separately)
- Chunks: ~615

## Test 6: Compare with nomic

```bash
cd /home/glenn/repos/testsc/opt/strac
rm -rf .ogrep
export OGREP_BASE_URL=http://localhost:1234/v1

time ogrep index . -m nomic --chunk-lines 30 --overlap 15 -e '*' -i cgpsv85.php
```

**Expected**: ~2-3x slower than minilm

## Troubleshooting

### If performance is slow

1. **Check GPU usage** (if applicable):
   ```bash
   nvidia-smi  # or equivalent
   ```

2. **Check LM Studio memory**:
   ```bash
   ~/.cache/lm-studio/bin/lms status
   ```

3. **Restart LM Studio server**:
   ```bash
   ~/.cache/lm-studio/bin/lms server stop
   ~/.cache/lm-studio/bin/lms server start --port 1234
   ```

4. **Reload model**:
   ```bash
   ~/.cache/lm-studio/bin/lms unload --all
   ~/.cache/lm-studio/bin/lms load all-MiniLM-L6-v2 -y
   ```

5. **Check system load**:
   ```bash
   htop  # or top
   ```

### If batching isn't working

1. Check `OGREP_BASE_URL` is set (batching only for local servers)
2. Check `OGREP_BATCH_SIZE` env var isn't set to a bad value
3. Verify `is_local=True` in auto-tuning test

## Performance Baseline (2026-01-12)

Record results after each test session:

| Date | Model | Short strings | PHP chunks | Notes |
|------|-------|---------------|------------|-------|
| 2026-01-12 (post-reboot) | minilm | 29ms/chunk | 38-50ms/chunk | ✓ All targets met |
| 2026-01-12 (post-reboot) | nomic | 39ms/chunk | 259ms/chunk | Much improved from 318ms |
| 2026-01-12 | minilm | 23ms/chunk | 72ms/chunk | After implementing batch chunking |
| 2026-01-12 | nomic | 318ms/chunk | - | Much slower |
| Previous | minilm | ~24ms/chunk | - | "Flew so fast" - target to match |

## Batch Size Findings (2026-01-12)

Testing with 200 real PHP chunks revealed:

| Batch Size | ms/chunk | vs Serial | Recommendation |
|------------|----------|-----------|----------------|
| 1 (serial) | 50.2ms | baseline | - |
| 4 | 41.2ms | 18% faster | - |
| 8 | 42.1ms | 16% faster | - |
| **16** | 42.1ms | 16% faster | **Default** |
| 32 | 40.6ms | 19% faster | Good |
| 64 | 39.0ms | 22% faster | Near context limits |
| 128 | 38.7ms | 23% faster | May exceed context |

**Key findings:**
- Embedding quality is **identical** across all batch sizes (cosine similarity = 1.0)
- Sweet spot is **batch size 16** - good speedup with safety margin
- Larger batches approach context limits (~8K tokens for most models)
- Default changed from 32 to 16 in `ogrep/embed.py`

## Success Criteria

Performance is considered acceptable if:
1. minilm achieves <50ms/chunk for real PHP code ✓ (38-50ms achieved)
2. Full index of cgpsv85.php completes in <60s ✓ (54.55s achieved)
3. No crashes or "model unloaded" errors ✓

## Next Steps After Testing

1. ~~If performance matches baseline: Document results, close investigation~~ **DONE**
2. If still slow: Check LM Studio logs, try different quantization, check thermal throttling
3. If inconsistent: May be related to model warm-up, queue depth, or memory pressure

## OpenAI Comparison (2026-01-12)

Testing with same PHP chunks (1230 chunks total):

| Batch Size | ms/chunk | vs Serial | Notes |
|------------|----------|-----------|-------|
| 1 (serial) | 258ms | baseline | Network overhead per request |
| 16 | 48ms | 5.4x faster | - |
| 50 | 18ms | 14x faster | - |
| 100 | 10ms | 26x faster | - |
| **200** | 6.7ms | **38x faster** | **New default for OpenAI** |

**Full index time:** 14.2s for 1230 chunks (vs 58s for minilm, 5:17 for nomic)

## Resolution

**Root cause**: Previous slow session (~72ms/chunk) was likely due to system state before reboot.
After fresh reboot, performance returned to expected levels (~38-50ms/chunk).

**Changes made:**
1. Added `context_tokens` and `max_batch_size` to all model definitions
2. Local models: default 16, max varies (16-32)
3. OpenAI models: default 200, max 2048
4. Auto-tuning now tests model-appropriate batch sizes:
   - Local: [8, 16, 32] capped to model max
   - OpenAI: [64, 128, 256, 512, 768, 1024, 2048]
5. `OGREP_BATCH_SIZE` environment override now capped to model's max
6. Investigation complete - performance optimized for both local and cloud models
