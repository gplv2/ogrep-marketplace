from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    start_line: int
    end_line: int
    text: str


def chunk_lines(text: str, chunk_size: int = 120, overlap: int = 20) -> List[Chunk]:
    lines = text.splitlines()
    out: List[Chunk] = []
    i = 0
    idx = 0

    while i < len(lines):
        start = i
        end = min(i + chunk_size, len(lines))
        chunk_text = "\n".join(lines[start:end]).strip()
        if chunk_text:
            out.append(
                Chunk(
                    chunk_index=idx,
                    start_line=start + 1,
                    end_line=end,
                    text=chunk_text,
                )
            )
            idx += 1

        if end == len(lines):
            break

        i = max(end - overlap, start + 1)

    return out
