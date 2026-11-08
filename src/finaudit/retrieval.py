"""Find the pages most relevant to a question.

Default: BM25, a keyword-ranking method. Financial questions usually share
exact terms with the filing ("research and development", "net sales"), and
BM25 handles that well with no model download and no cost.

Optional: dense embeddings (sentence-transformers) for paraphrased questions.
Page embeddings are computed once and cached to disk, not on every query.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

import numpy as np

from .document import Page

TOKEN = re.compile(r"[a-z0-9]+")
STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "is", "was", "what",
        "did", "does", "how", "much", "many", "its", "it", "company", "s", "by", "at", "as"}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


class BM25Retriever:
    def __init__(self, pages: list[Page], k1: float = 1.5, b: float = 0.75):
        self.pages = pages
        self.docs = [Counter(tokenize(p.text)) for p in pages]
        self.lengths = np.array([sum(d.values()) for d in self.docs], float)
        self.avg_len = self.lengths.mean() if len(pages) else 0.0
        n = len(pages)
        df = Counter(term for d in self.docs for term in d)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query: str) -> np.ndarray:
        q = tokenize(query)
        s = np.zeros(len(self.pages))
        for i, d in enumerate(self.docs):
            norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg_len)
            for t in q:
                tf = d.get(t, 0)
                if tf:
                    s[i] += self.idf[t] * tf * (self.k1 + 1) / (tf + norm)
        return s

    def top_k(self, query: str, k: int) -> list[Page]:
        s = self.scores(query)
        order = np.argsort(-s)[:k]
        return [self.pages[i] for i in order if s[i] > 0]


class EmbeddingRetriever:
    """Dense retrieval with all-MiniLM-L6-v2. Requires `pip install sentence-transformers`."""

    MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, pages: list[Page], cache: Path):
        from sentence_transformers import SentenceTransformer
        self.pages = pages
        self.model = SentenceTransformer(self.MODEL)
        if cache.exists():
            self.emb = np.load(cache)
        else:
            self.emb = self.model.encode([p.text for p in pages], normalize_embeddings=True)
            np.save(cache, self.emb)

    def top_k(self, query: str, k: int) -> list[Page]:
        q = self.model.encode([query], normalize_embeddings=True)[0]
        order = np.argsort(-(self.emb @ q))[:k]
        return [self.pages[i] for i in order]
