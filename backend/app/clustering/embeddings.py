"""Text embedding backends. TF-IDF is the default (no torch, fits free-tier RAM); sentence-transformers is optional."""
import re
from typing import Protocol

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.services.adapters.base import AdapterError


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> object: ...


class TfidfEmbedder:
    """Character n-gram TF-IDF. Sparse, L2-normalised; captures wording and formatting structure, not deep semantics."""
    name = "tfidf-char_wb-2-4"

    def embed(self, texts: list[str]) -> object:
        return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True).fit_transform(texts)


class SentenceTransformerEmbedder:
    name = "sentence-transformers/all-MiniLM-L6-v2"

    def embed(self, texts: list[str]) -> object:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        except ImportError as exc:
            raise AdapterError("EMBEDDINGS_BACKEND=sentence-transformers needs: pip install -r requirements-ml.txt") from exc
        return np.asarray(SentenceTransformer("all-MiniLM-L6-v2").encode(texts, normalize_embeddings=True))


def get_embedder(backend: str) -> Embedder:
    return SentenceTransformerEmbedder() if backend == "sentence-transformers" else TfidfEmbedder()


def normalise_for_embedding(text: str) -> str:
    """Digits carry no structural meaning for grouping failures, so map them to '0'."""
    return re.sub(r"\d", "0", text)
