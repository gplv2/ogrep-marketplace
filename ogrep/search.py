"""
Search module for ogrep.

Provides semantic search functionality by computing cosine similarity
between a query embedding and stored chunk embeddings. Supports both
numpy (fast) and pure Python (fallback) implementations.

Search modes:
    - semantic: Embedding similarity only (original behavior)
    - fulltext: SQLite FTS5 keyword matching only
    - hybrid: Combined score (default) - best of both worlds

Hybrid fusion methods:
    - rrf (default): Reciprocal Rank Fusion - combines results by rank position.
      More robust than score weighting since it doesn't depend on score scales.
      Formula: score = 1/(k + semantic_rank) + 1/(k + fts_rank), where k=60.

    - alpha: Linear weighted combination of normalized scores.
      Formula: score = alpha * semantic_score + (1 - alpha) * fts_score.
      Legacy method, available for comparison.

Confidence scoring:
    Results include a confidence level (high/medium/low/very_low) that
    indicates match quality. Two modes are available:

    - relative (default): Compares each score to the top result.
      More meaningful since cosine similarity clusters around 0.3-0.5.
      A score of 0.40 that's 90% of the top score (0.44) = "high".

    - absolute: Uses fixed thresholds (legacy behavior).
      Less meaningful for typical embedding distributions.

Environment variables:
    OGREP_SEARCH_MODE: Default search mode (semantic, fulltext, hybrid)
    OGREP_FUSION_METHOD: Hybrid fusion method ("rrf" or "alpha", default: "rrf")
    OGREP_HYBRID_ALPHA: Semantic weight for alpha fusion (0.0-1.0, default: 0.7)
    OGREP_RRF_K: RRF rank constant (default: 60, higher = more weight to lower ranks)
    OGREP_CONFIDENCE_MODE: "relative" (default) or "absolute"
    OGREP_RELATIVE_HIGH: Fraction of top score for "high" (default: 0.90)
    OGREP_RELATIVE_MEDIUM: Fraction of top score for "medium" (default: 0.75)
    OGREP_RELATIVE_LOW: Fraction of top score for "low" (default: 0.50)
    OGREP_CONFIDENCE_HIGH: Absolute threshold for "high" (default: 0.50)
    OGREP_CONFIDENCE_MEDIUM: Absolute threshold for "medium" (default: 0.40)
    OGREP_CONFIDENCE_LOW: Absolute threshold for "low" (default: 0.30)
"""

from __future__ import annotations

import array
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .db import connect, has_fts5
from .embed import embed_texts
from .models import MODEL_ALIASES

# Optional numpy for faster similarity calculations
try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]

# Search mode type
SearchMode = Literal["semantic", "fulltext", "hybrid"]

# Default search mode from environment
DEFAULT_SEARCH_MODE: SearchMode = os.environ.get("OGREP_SEARCH_MODE", "hybrid")  # type: ignore[assignment]

# Fusion method for hybrid search: "rrf" (default) or "alpha" (legacy)
# RRF is more robust since it uses ranks instead of scores
FUSION_METHOD = os.environ.get("OGREP_FUSION_METHOD", "rrf").lower()

# Hybrid scoring weight for alpha fusion (0.0-1.0, 1.0 = all semantic, 0.0 = all fulltext)
HYBRID_ALPHA = float(os.environ.get("OGREP_HYBRID_ALPHA", "0.7"))

# RRF constant k (default: 60, standard in literature)
# Higher k = more weight to lower-ranked results, smoother ranking
RRF_K = int(os.environ.get("OGREP_RRF_K", "60"))

# Confidence mode: "relative" (percentile-based, default) or "absolute" (threshold-based)
# Relative mode compares scores to the top result, which is more meaningful since
# cosine similarity for text embeddings clusters around 0.3-0.5, not uniformly [0,1]
CONFIDENCE_MODE = os.environ.get("OGREP_CONFIDENCE_MODE", "relative")

# Absolute confidence thresholds (calibrated for typical embedding distributions)
# These are used when OGREP_CONFIDENCE_MODE=absolute
CONFIDENCE_HIGH = float(os.environ.get("OGREP_CONFIDENCE_HIGH", "0.50"))
CONFIDENCE_MEDIUM = float(os.environ.get("OGREP_CONFIDENCE_MEDIUM", "0.40"))
CONFIDENCE_LOW = float(os.environ.get("OGREP_CONFIDENCE_LOW", "0.30"))

# Relative confidence thresholds (as percentage of top score)
# These define what fraction of the top score qualifies for each level
RELATIVE_HIGH = float(os.environ.get("OGREP_RELATIVE_HIGH", "0.90"))  # >= 90% of top
RELATIVE_MEDIUM = float(os.environ.get("OGREP_RELATIVE_MEDIUM", "0.75"))  # >= 75% of top
RELATIVE_LOW = float(os.environ.get("OGREP_RELATIVE_LOW", "0.50"))  # >= 50% of top


def get_confidence_level(score: float) -> str:
    """
    Convert numeric score to human-readable confidence level (absolute mode).

    Uses configurable thresholds from environment variables:
        OGREP_CONFIDENCE_HIGH: Threshold for "high" (default: 0.85)
        OGREP_CONFIDENCE_MEDIUM: Threshold for "medium" (default: 0.70)
        OGREP_CONFIDENCE_LOW: Threshold for "low" (default: 0.50)

    Args:
        score: Similarity score (0.0 to 1.0).

    Returns:
        Confidence level: "high", "medium", "low", or "very_low".
    """
    if score >= CONFIDENCE_HIGH:
        return "high"
    elif score >= CONFIDENCE_MEDIUM:
        return "medium"
    elif score >= CONFIDENCE_LOW:
        return "low"
    else:
        return "very_low"


def get_relative_confidence(score: float, top_score: float) -> str:
    """
    Convert numeric score to confidence level relative to top result.

    Instead of absolute thresholds, this compares the score to the best
    match in the result set. This accounts for the fact that cosine
    similarity scores for text embeddings cluster around 0.3-0.5, making
    absolute thresholds misleading.

    Uses configurable thresholds from environment variables:
        OGREP_RELATIVE_HIGH: Fraction of top score for "high" (default: 0.90)
        OGREP_RELATIVE_MEDIUM: Fraction of top score for "medium" (default: 0.75)
        OGREP_RELATIVE_LOW: Fraction of top score for "low" (default: 0.50)

    Args:
        score: Similarity score for this result.
        top_score: Highest score in the result set.

    Returns:
        Confidence level: "high", "medium", "low", or "very_low".

    Example:
        If top_score=0.45 and score=0.42:
        - ratio = 0.42/0.45 = 0.93 (93% of top)
        - Since 0.93 >= 0.90, this is "high" confidence

        This is more meaningful than absolute scoring, where 0.42
        might appear as "low" despite being nearly as good as the
        best match.
    """
    if top_score <= 0:
        return "very_low"

    ratio = score / top_score

    if ratio >= RELATIVE_HIGH:
        return "high"
    elif ratio >= RELATIVE_MEDIUM:
        return "medium"
    elif ratio >= RELATIVE_LOW:
        return "low"
    else:
        return "very_low"


def assign_confidence(score: float, top_score: float | None = None) -> str:
    """
    Assign confidence level based on current mode (absolute or relative).

    Args:
        score: Similarity score for this result.
        top_score: Highest score in result set (required for relative mode).

    Returns:
        Confidence level: "high", "medium", "low", or "very_low".
    """
    if CONFIDENCE_MODE == "relative" and top_score is not None:
        return get_relative_confidence(score, top_score)
    else:
        return get_confidence_level(score)


@dataclass(frozen=True)
class Hit:
    """
    A search result representing a matching code chunk.

    Attributes:
        score: Cosine similarity score (0.0 to 1.0, higher is better).
        path: Absolute path to the source file.
        start_line: First line number of the chunk (1-indexed).
        end_line: Last line number of the chunk (inclusive).
        text: The actual text content of the chunk.
        chunk_id: Internal database ID for the chunk.
        chunk_index: Index of this chunk within its file (0-indexed).
        confidence: Human-readable confidence level based on score.
    """

    score: float
    path: str
    start_line: int
    end_line: int
    text: str
    chunk_id: int
    chunk_index: int
    confidence: str


def _dot_py(a: array.array, b: array.array) -> float:
    """
    Compute dot product using pure Python (fallback when numpy unavailable).

    Args:
        a: First vector as float32 array.
        b: Second vector as float32 array.

    Returns:
        Dot product of the two vectors.
    """
    s = 0.0
    for x, y in zip(a, b, strict=True):
        s += float(x) * float(y)
    return s


def _escape_fts5_query(q: str) -> str:
    """
    Escape special characters for FTS5 query.

    FTS5 has special syntax characters that need escaping.
    We quote each term to handle special characters.

    Args:
        q: Raw query string.

    Returns:
        Escaped query safe for FTS5 MATCH.
    """
    # Split into words and quote each term
    # This handles underscores, dots, and other special chars
    terms = q.split()
    return " ".join(f'"{term}"' for term in terms)


def _rrf_score(
    semantic_rank: int | None,
    fts_rank: int | None,
    k: int = 60,
) -> float:
    """
    Compute Reciprocal Rank Fusion (RRF) score.

    RRF combines results from multiple ranking systems by using their
    rank positions rather than raw scores. This is more robust because:
    - Scores from different systems have different distributions
    - Ranks are comparable across systems
    - No need to tune weighting parameters

    Formula: RRF(d) = sum(1 / (k + rank_i)) for each ranking system i

    The k parameter (default 60) controls how much weight is given to
    lower-ranked results. Higher k = smoother distribution.

    Reference: Cormack, Clarke, Buettcher. "Reciprocal Rank Fusion
    outperforms Condorcet and individual Rank Learning Methods" (SIGIR 2009)

    Args:
        semantic_rank: 1-indexed rank from semantic search (None if not ranked).
        fts_rank: 1-indexed rank from full-text search (None if not ranked).
        k: Rank constant (default: 60, standard in literature).

    Returns:
        Combined RRF score (higher is better).

    Example:
        >>> _rrf_score(1, 3)  # Top semantic, 3rd in FTS
        0.032258...  # 1/(60+1) + 1/(60+3)
        >>> _rrf_score(10, None)  # Only in semantic results
        0.014285...  # 1/(60+10)
    """
    score = 0.0
    if semantic_rank is not None:
        score += 1.0 / (k + semantic_rank)
    if fts_rank is not None:
        score += 1.0 / (k + fts_rank)
    return score


def _fulltext_search(
    con,
    q: str,
    top_k: int,
) -> tuple[dict[int, float], dict[int, int]]:
    """
    Perform FTS5 full-text search and return normalized BM25 scores and ranks.

    Args:
        con: Database connection.
        q: Search query string.
        top_k: Maximum number of results.

    Returns:
        Tuple of (scores, ranks):
        - scores: Dict mapping chunk_id to normalized score (0.0 to 1.0).
        - ranks: Dict mapping chunk_id to 1-indexed rank position.
    """
    # Escape query for FTS5 syntax
    escaped_q = _escape_fts5_query(q)

    # FTS5 bm25() returns negative scores (lower is better)
    # We need to normalize them to positive scores (higher is better)
    try:
        rows = con.execute(
            """SELECT rowid, bm25(chunks_fts) as rank
               FROM chunks_fts
               WHERE text MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (escaped_q, top_k * 2),  # Fetch extra for hybrid merging
        ).fetchall()
    except Exception:
        # If FTS5 query fails for any reason, return empty results
        return {}, {}

    if not rows:
        return {}, {}

    # Normalize BM25 scores to 0.0-1.0 range
    # BM25 scores are negative, so we invert and normalize
    scores = [-r[1] for r in rows]  # Make positive
    max_score = max(scores) if scores else 1.0
    min_score = min(scores) if scores else 0.0
    score_range = max_score - min_score if max_score != min_score else 1.0

    score_dict = {row[0]: ((-row[1]) - min_score) / score_range for row in rows}
    # Ranks are 1-indexed (1 = best match)
    rank_dict = {row[0]: i + 1 for i, row in enumerate(rows)}

    return score_dict, rank_dict


def query(
    db_path: Path,
    q: str,
    top_k: int = 10,
    model: str = "text-embedding-3-small",
    dimensions: int | None = None,
    mode: SearchMode | None = None,
) -> tuple[list[Hit], bool]:
    """
    Perform search against the indexed codebase.

    Supports three search modes:
    - semantic: Embedding similarity only (original behavior)
    - fulltext: SQLite FTS5 keyword matching only
    - hybrid: Combined score (default) - best of both worlds

    Args:
        db_path: Path to the SQLite database.
        q: Natural language query string.
        top_k: Maximum number of results to return (default: 10).
        model: OpenAI embedding model. Must match the model used during
            indexing for meaningful results.
        dimensions: Embedding dimensions. Must match indexing dimensions.
        mode: Search mode (semantic, fulltext, hybrid). Default from
            OGREP_SEARCH_MODE env var or "hybrid".

    Returns:
        Tuple of (hits, fts_available):
        - hits: List of Hit objects sorted by descending score.
        - fts_available: Whether FTS5 was available for this search.

    Note:
        Uses numpy for similarity calculations if available, falling
        back to pure Python otherwise. Numpy is ~10x faster for large
        indexes.

        If FTS5 is unavailable and mode is hybrid/fulltext, falls back
        to semantic search and returns fts_available=False.

    Example:
        >>> hits, fts_ok = query(Path(".ogrep/index.sqlite"), "database connection")
        >>> for h in hits[:3]:
        ...     print(f"{h.path}:{h.start_line} (score={h.score:.3f})")
    """
    if mode is None:
        mode = DEFAULT_SEARCH_MODE

    con = connect(db_path, init_fts=False)

    # Check for mixed dimensions (corrupted index)
    distinct_dims = con.execute("SELECT DISTINCT dim FROM chunks").fetchall()
    if len(distinct_dims) > 1:
        dims_list = sorted([d[0] for d in distinct_dims])
        raise ValueError(
            f"Corrupted index: mixed dimensions detected ({dims_list}). "
            f"This can happen if --refresh was run with a different model. "
            f"Run 'ogrep reset -f && ogrep index .' to rebuild."
        )

    # Check index model/dimensions before querying
    index_info = con.execute("SELECT model, dim FROM chunks LIMIT 1").fetchone()
    if index_info is None:
        return [], True  # Empty index

    index_model, index_dim = index_info

    # Check FTS5 availability
    fts_available = has_fts5(con)

    # Determine effective mode (fallback to semantic if FTS5 unavailable)
    effective_mode = mode
    if mode in ("hybrid", "fulltext") and not fts_available:
        effective_mode = "semantic"

    # Full-text only mode
    if effective_mode == "fulltext":
        fts_scores, _ = _fulltext_search(con, q, top_k)
        if not fts_scores:
            return [], fts_available

        # Fetch chunk details for FTS matches
        chunk_ids = list(fts_scores.keys())
        placeholders = ",".join("?" * len(chunk_ids))
        rows = con.execute(
            f"""SELECT c.id, c.chunk_index, f.path, c.start_line, c.end_line, c.text
                FROM chunks c
                JOIN files f ON f.id = c.file_id
                WHERE c.id IN ({placeholders})""",
            chunk_ids,
        ).fetchall()

        # Build hits with scores, sorted by score descending
        scored_rows = sorted(
            [(fts_scores[row[0]], row) for row in rows],
            key=lambda x: x[0],
            reverse=True,
        )[:top_k]

        # Get top score for relative confidence
        top_score = scored_rows[0][0] if scored_rows else 0.0

        hits = [
            Hit(
                score=score,
                path=row[2],
                start_line=int(row[3]),
                end_line=int(row[4]),
                text=row[5],
                chunk_id=int(row[0]),
                chunk_index=int(row[1]),
                confidence=assign_confidence(score, top_score),
            )
            for score, row in scored_rows
        ]
        return hits, fts_available

    # Semantic search (needed for semantic and hybrid modes)
    # Embed the query
    q_blob, q_dim = embed_texts([q], model=model, dimensions=dimensions)
    q_arr = array.array("f")
    q_arr.frombytes(q_blob[0])

    # Validate dimensions match
    if q_dim != index_dim:
        # Reverse lookup for model aliases (prefer shortest alias)
        alias_lookup: dict[str, str] = {}
        for alias, full_name in MODEL_ALIASES.items():
            if full_name not in alias_lookup or len(alias) < len(alias_lookup[full_name]):
                alias_lookup[full_name] = alias
        index_alias = alias_lookup.get(index_model, index_model)
        query_alias = alias_lookup.get(model, model)
        raise ValueError(
            f"Dimension mismatch: query uses {q_dim}D ({model}) "
            f"but index was built with {index_dim}D ({index_model}). "
            f"Use -m {index_alias} or reindex with -m {query_alias}."
        )

    # Fetch all chunks
    rows = con.execute(
        """SELECT c.id, c.chunk_index, f.path, c.start_line, c.end_line, c.text, c.embedding
           FROM chunks c
           JOIN files f ON f.id = c.file_id"""
    ).fetchall()

    # Get FTS scores and ranks if in hybrid mode
    fts_scores: dict[int, float] = {}
    fts_ranks: dict[int, int] = {}
    if effective_mode == "hybrid" and fts_available:
        fts_scores, fts_ranks = _fulltext_search(con, q, top_k * 2)

    # Step 1: Compute semantic scores for all chunks
    # Store as (semantic_score, chunk_id, chunk_idx, path, sl, el, text)
    semantic_results: list[tuple[float, int, int, str, int, int, str]] = []

    if np is not None:
        # Fast path with numpy
        qv = np.frombuffer(q_blob[0], dtype=np.float32)
        for chunk_id, chunk_idx, path, sl, el, text, emb in rows:
            v = np.frombuffer(emb, dtype=np.float32)
            semantic_score = float(np.dot(qv, v))  # cosine similarity
            semantic_results.append(
                (semantic_score, int(chunk_id), int(chunk_idx), path, int(sl), int(el), text)
            )
    else:
        # Fallback pure Python
        for chunk_id, chunk_idx, path, sl, el, text, emb in rows:
            v = array.array("f")
            v.frombytes(emb)
            semantic_score = _dot_py(q_arr, v)
            semantic_results.append(
                (semantic_score, int(chunk_id), int(chunk_idx), path, int(sl), int(el), text)
            )

    # Step 2: Sort by semantic score to get semantic ranks
    semantic_results.sort(key=lambda x: x[0], reverse=True)

    # Build semantic rank lookup (1-indexed)
    semantic_ranks: dict[int, int] = {}
    for rank, (_, chunk_id, *_rest) in enumerate(semantic_results, start=1):
        semantic_ranks[chunk_id] = rank

    # Step 3: Compute final scores based on fusion method
    scored_results: list[tuple[float, int, int, str, int, int, str]] = []

    if effective_mode == "hybrid" and (fts_scores or fts_ranks):
        # Hybrid mode: combine semantic and FTS results
        use_rrf = FUSION_METHOD == "rrf"

        # Collect all chunk IDs that appear in either result set
        all_chunk_ids = set(semantic_ranks.keys())
        if fts_ranks:
            all_chunk_ids.update(fts_ranks.keys())

        # Build lookup for chunk details
        chunk_details = {
            chunk_id: (chunk_idx, path, sl, el, text)
            for (_, chunk_id, chunk_idx, path, sl, el, text) in semantic_results
        }

        for chunk_id in all_chunk_ids:
            if chunk_id not in chunk_details:
                continue  # Skip if we don't have chunk details

            chunk_idx, path, sl, el, text = chunk_details[chunk_id]
            sem_rank = semantic_ranks.get(chunk_id)
            fts_rank = fts_ranks.get(chunk_id)

            if use_rrf:
                # RRF fusion: combine by ranks
                score = _rrf_score(sem_rank, fts_rank, k=RRF_K)
            else:
                # Alpha fusion: combine by scores (legacy)
                sem_score = next(
                    (s for s, cid, *_ in semantic_results if cid == chunk_id), 0.0
                )
                fts_score = fts_scores.get(chunk_id, 0.0)
                score = HYBRID_ALPHA * sem_score + (1 - HYBRID_ALPHA) * fts_score

            scored_results.append(
                (score, chunk_id, chunk_idx, path, sl, el, text)
            )
    else:
        # Semantic-only mode: use semantic scores directly
        scored_results = list(semantic_results)

    # Sort by final score descending and take top-k
    scored_results.sort(key=lambda x: x[0], reverse=True)
    top_results = scored_results[:top_k]

    # Get top score for relative confidence calculation
    top_score = top_results[0][0] if top_results else 0.0

    # Build final Hit objects with confidence
    hits = [
        Hit(
            score=score,
            path=path,
            start_line=sl,
            end_line=el,
            text=text,
            chunk_id=chunk_id,
            chunk_index=chunk_idx,
            confidence=assign_confidence(score, top_score),
        )
        for score, chunk_id, chunk_idx, path, sl, el, text in top_results
    ]

    return hits, fts_available
