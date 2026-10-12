"""RAG leve: TF-IDF + similaridade de cosseno em Python puro, sobre runbooks em Markdown.

Sem banco vetorial nem embeddings: para um corpus pequeno e vocabulário técnico
específico, recuperação lexical é suficiente, determinística e sem custo extra.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

from .config import RUNBOOKS_DIR

_STOP = {"de", "da", "do", "e", "o", "a", "que", "em", "um", "uma", "para", "com", "se", "no", "na",
         "the", "of", "and", "to", "is", "in", "it", "for", "on", "as", "ou", "os", "as", "por"}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if t not in _STOP and len(t) > 1]


@lru_cache(maxsize=1)
def _index() -> tuple[list[dict], dict[str, float]]:
    chunks: list[dict] = []
    for path in sorted(RUNBOOKS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for block in re.split(r"(?m)^## ", text)[1:]:
            title, _, body = block.partition("\n")
            body = body.strip()
            if body:
                chunks.append({"source": path.name, "section": title.strip(), "text": body})
    df: Counter = Counter()
    for c in chunks:
        c["tf"] = Counter(_tokens(c["section"] + " " + c["text"]))
        df.update(c["tf"].keys())
    n = max(len(chunks), 1)
    idf = {t: math.log((n + 1) / (d + 0.5)) + 1 for t, d in df.items()}
    return chunks, idf


def search(query: str, k: int = 3) -> list[dict]:
    chunks, idf = _index()
    q = Counter(_tokens(query))
    if not chunks or not q:
        return []
    scored = []
    for c in chunks:
        dot = sum(q[t] * idf.get(t, 0) * c["tf"][t] * idf.get(t, 0) for t in q if t in c["tf"])
        norm = math.sqrt(sum((v * idf[t]) ** 2 for t, v in c["tf"].items())) or 1
        if dot > 0:
            scored.append((dot / norm, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"fonte": f"{c['source']}#{c['section']}", "score": round(s, 3), "trecho": c["text"][:900]}
        for s, c in scored[:k]
    ]
