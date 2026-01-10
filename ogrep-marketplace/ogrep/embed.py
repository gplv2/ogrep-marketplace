from __future__ import annotations

import array
import math

from openai import OpenAI


def _l2_normalize(vec: list[float]) -> list[float]:
    s = 0.0
    for x in vec:
        s += x * x
    n = math.sqrt(s) if s > 0 else 1.0
    return [x / n for x in vec]


def embed_texts(
    texts: list[str],
    model: str = "text-embedding-3-small",
    dimensions: int | None = None,
) -> tuple[list[bytes], int]:
    """Return (list_of_embedding_blobs_float32, dim)."""
    client = OpenAI()

    kwargs = {"input": texts, "model": model}
    if dimensions is not None:
        kwargs["dimensions"] = dimensions

    resp = client.embeddings.create(**kwargs)

    vectors: list[bytes] = []
    dim: int | None = None
    for item in resp.data:
        v = _l2_normalize(list(item.embedding))
        if dim is None:
            dim = len(v)
        arr_f = array.array("f", v)  # float32
        vectors.append(arr_f.tobytes())

    assert dim is not None
    return vectors, dim
