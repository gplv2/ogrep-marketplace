from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, Optional

from tqdm import tqdm

from .chunking import chunk_lines
from .db import connect
from .embed import embed_texts

DEFAULT_SKIP_DIRS = {".git", ".venv", "node_modules", ".ogrep", "__pycache__"}


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _is_probably_text(b: bytes) -> bool:
    return b.find(b"\x00") == -1


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_SKIP_DIRS]
        for fn in filenames:
            yield Path(dirpath) / fn


def index_path(
    root: Path,
    db_path: Path,
    model: str = "text-embedding-3-small",
    dimensions: Optional[int] = None,
    chunk_lines: int = 120,
    overlap: int = 20,
    max_bytes: int = 2_000_000,
) -> None:
    con = connect(db_path)

    files = list(iter_files(root))
    for p in tqdm(files, desc="Indexing"):
        if not p.is_file():
            continue

        try:
            st = p.stat()
        except FileNotFoundError:
            continue

        if st.st_size > max_bytes:
            continue

        try:
            b = p.read_bytes()
        except Exception:
            continue

        if not _is_probably_text(b):
            continue

        sha = _sha256_bytes(b)
        rel = str(p.resolve())

        row = con.execute(
            "SELECT id, mtime_ns, size, sha256 FROM files WHERE path=?",
            (rel,),
        ).fetchone()

        if row and int(row[1]) == st.st_mtime_ns and int(row[2]) == st.st_size and str(row[3]) == sha:
            continue  # unchanged

        if row:
            file_id = int(row[0])
            con.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
            con.execute(
                "UPDATE files SET mtime_ns=?, size=?, sha256=? WHERE id=?",
                (st.st_mtime_ns, st.st_size, sha, file_id),
            )
        else:
            cur = con.execute(
                "INSERT INTO files(path, mtime_ns, size, sha256) VALUES(?,?,?,?)",
                (rel, st.st_mtime_ns, st.st_size, sha),
            )
            file_id = int(cur.lastrowid)

        text = b.decode("utf-8", errors="ignore")
        chunks = chunk_lines(text, chunk_size=chunk_lines, overlap=overlap)
        if not chunks:
            continue

        texts = [c.text.replace("\r\n", "\n") for c in chunks]
        emb_blobs, dim = embed_texts(texts, model=model, dimensions=dimensions)

        for c, emb in zip(chunks, emb_blobs):
            tsha = hashlib.sha256(c.text.encode("utf-8", errors="ignore")).hexdigest()
            con.execute(
                """INSERT INTO chunks(file_id, chunk_index, start_line, end_line, text, text_sha256, embedding, dim, model)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (file_id, c.chunk_index, c.start_line, c.end_line, c.text, tsha, emb, dim, model),
            )

        con.commit()
