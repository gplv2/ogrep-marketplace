from __future__ import annotations

import array
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .db import connect
from .embed import embed_texts

try:
    import numpy as np  # optional
except Exception:
    np = None


@dataclass(frozen=True)
class Hit:
    score: float
    path: str
    start_line: int
    end_line: int
    text: str


def _dot_py(a: array.array, b: array.array) -> float:
    s = 0.0
    for x, y in zip(a, b):
        s += float(x) * float(y)
    return s


def query(
    db_path: Path,
    q: str,
    top_k: int = 10,
    model: str = "text-embedding-3-small",
    dimensions: Optional[int] = None,
) -> List[Hit]:
    con = connect(db_path)

    q_blob, _ = embed_texts([q], model=model, dimensions=dimensions)
    q_arr = array.array("f")
    q_arr.frombytes(q_blob[0])

    rows = con.execute(
        """SELECT f.path, c.start_line, c.end_line, c.text, c.embedding
           FROM chunks c
           JOIN files f ON f.id = c.file_id"""
    ).fetchall()

    hits: List[Hit] = []
    if np is not None:
        qv = np.frombuffer(q_blob[0], dtype=np.float32)
        for path, sl, el, text, emb in rows:
            v = np.frombuffer(emb, dtype=np.float32)
            score = float(np.dot(qv, v))  # cosine if normalized
            hits.append(Hit(score=score, path=path, start_line=int(sl), end_line=int(el), text=text))
    else:
        for path, sl, el, text, emb in rows:
            v = array.array("f")
            v.frombytes(emb)
            score = _dot_py(q_arr, v)
            hits.append(Hit(score=score, path=path, start_line=int(sl), end_line=int(el), text=text))

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]
