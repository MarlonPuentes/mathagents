"""Modelos de embeddings: texto -> vector de números normalizado (norma 1).

- HashingEmbedder: sin descargas ni GPU. Cuenta palabras y pedazos de palabras
  con un "hash" fijo. Es simple y determinista: sirve para PRUEBAS, no es un
  modelo semántico de verdad.
- SentenceTransformerEmbedder: modelo Transformer real (ej. BAAI/bge-small-en-v1.5).
  Es el que se usa en los experimentos (RF-2).
"""
from __future__ import annotations

import hashlib
import re

import numpy as np


def humanize_lean_name(name: str) -> str:
    """'Nat.succ_le_iff' -> 'Nat succ le iff' para que el modelo lea palabras."""
    return re.sub(r"[._]", " ", name)


def lemma_to_text(name: str, statement: str) -> str:
    return f"{humanize_lean_name(name)} : {statement}"


class HashingEmbedder:
    name = "hashing-v1"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _features(self, text: str) -> list[str]:
        tokens = re.findall(r"[A-Za-z]+|\d+|[^\sA-Za-z\d]", text.lower())
        grams = [t[i:i + 3] for t in tokens if len(t) > 3 for i in range(len(t) - 2)]
        return tokens + grams

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feat in self._features(text):
                h = int.from_bytes(hashlib.md5(feat.encode("utf-8")).digest()[:4], "little")
                out[row, h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, revision: str | None = None, batch_size: int = 64):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError("Instala: pip install sentence-transformers") from exc
        self.name = f"{model_name}@{revision or 'main'}"
        self._model = SentenceTransformer(model_name, revision=revision, device="cpu")
        self.dim = self._model.get_sentence_embedding_dimension()
        self.batch_size = batch_size

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                  show_progress_bar=len(texts) > 1000, convert_to_numpy=True)
        return vecs.astype(np.float32)


def create_embedder(cfg: dict):
    r = cfg["retrieval"]
    if r["embedder"] == "hashing":
        return HashingEmbedder()
    if r["embedder"] == "sentence_transformers":
        return SentenceTransformerEmbedder(r["model_name"], r.get("model_revision"))
    raise ValueError(f"Embedder desconocido: {r['embedder']}")
