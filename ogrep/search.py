"""
Search module for ogrep.

Provides semantic search functionality by computing cosine similarity
between a query embedding and stored chunk embeddings. Supports both
numpy (fast) and pure Python (fallback) implementations.
"""

from __future__ import annotations

import array
from dataclasses import dataclass
from pathlib import Path

from .db import connect
from .embed import embed_texts
from .models import MODEL_ALIASES

# Optional numpy for faster similarity calculations
try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]


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
    """

    score: float
    path: str
    start_line: int
    end_line: int
    text: str


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


def query(
    db_path: Path,
    q: str,
    top_k: int = 10,
    model: str = "text-embedding-3-small",
    dimensions: int | None = None,
) -> list[Hit]:
    """
    Perform semantic search against the indexed codebase.

    Embeds the query text and computes cosine similarity against all
    stored chunks, returning the top-k most similar results.

    Args:
        db_path: Path to the SQLite database.
        q: Natural language query string.
        top_k: Maximum number of results to return (default: 10).
        model: OpenAI embedding model. Must match the model used during
            indexing for meaningful results.
        dimensions: Embedding dimensions. Must match indexing dimensions.

    Returns:
        List of Hit objects sorted by descending similarity score.

    Note:
        Uses numpy for similarity calculations if available, falling
        back to pure Python otherwise. Numpy is ~10x faster for large
        indexes.

    Example:
        >>> hits = query(Path(".ogrep/index.sqlite"), "database connection")
        >>> for h in hits[:3]:
        ...     print(f"{h.path}:{h.start_line} (score={h.score:.3f})")
    """
    con = connect(db_path)

    # Check index model/dimensions before querying
    index_info = con.execute("SELECT model, dim FROM chunks LIMIT 1").fetchone()
    if index_info is None:
        return []  # Empty index

    index_model, index_dim = index_info

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
        """SELECT f.path, c.start_line, c.end_line, c.text, c.embedding
           FROM chunks c
           JOIN files f ON f.id = c.file_id"""
    ).fetchall()

    # Compute similarities
    hits: list[Hit] = []
    if np is not None:
        # Fast path with numpy
        qv = np.frombuffer(q_blob[0], dtype=np.float32)
        for path, sl, el, text, emb in rows:
            v = np.frombuffer(emb, dtype=np.float32)
            score = float(np.dot(qv, v))  # cosine similarity (vectors are normalized)
            hits.append(
                Hit(score=score, path=path, start_line=int(sl), end_line=int(el), text=text)
            )
    else:
        # Fallback pure Python
        for path, sl, el, text, emb in rows:
            v = array.array("f")
            v.frombytes(emb)
            score = _dot_py(q_arr, v)
            hits.append(
                Hit(score=score, path=path, start_line=int(sl), end_line=int(el), text=text)
            )

    # Sort by score descending and return top-k
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]
