"""Índice vectorial sobre los lemas de Mathlib (RF-2).

Guarda en disco:
  vectors.npy   -> matriz (n_lemas x dim), cada fila normalizada
  lemmas.jsonl  -> nombre, enunciado y módulo de cada lema (misma posición)
  meta.json     -> modelo de embeddings usado, dimensión, fecha (RNF-2)
Búsqueda: similitud coseno = producto punto (porque los vectores tienen norma 1).
Usa FAISS si está instalado; si no, numpy (mismo resultado, más lento).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover
    faiss = None


class VectorIndex:
    def __init__(self, vectors: np.ndarray, lemmas: list[dict], embedder_name: str):
        if len(vectors) != len(lemmas):
            raise ValueError("vectors y lemmas deben tener el mismo largo")
        self.vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self.lemmas = lemmas
        self.embedder_name = embedder_name
        self._faiss = None
        if faiss is not None and len(vectors):
            self._faiss = faiss.IndexFlatIP(self.vectors.shape[1])
            self._faiss.add(self.vectors)

    @classmethod
    def build(cls, lemmas: list[dict], embedder, text_fn) -> "VectorIndex":
        texts = [text_fn(l["name"], l["statement"]) for l in lemmas]
        return cls(embedder.encode(texts), lemmas, embedder.name)

    def search(self, query_vec: np.ndarray, k: int) -> list[tuple[int, float]]:
        k = min(k, len(self.lemmas))
        if k == 0:
            return []
        q = np.ascontiguousarray(query_vec.reshape(1, -1), dtype=np.float32)
        if self._faiss is not None:
            scores, idx = self._faiss.search(q, k)
            return [(int(i), float(s)) for i, s in zip(idx[0], scores[0]) if i >= 0]
        sims = self.vectors @ q[0]
        top = np.argsort(-sims, kind="stable")[:k]
        return [(int(i), float(sims[i])) for i in top]

    def save(self, directory: str | Path) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        np.save(d / "vectors.npy", self.vectors)
        with open(d / "lemmas.jsonl", "w", encoding="utf-8") as fh:
            for l in self.lemmas:
                fh.write(json.dumps(l, ensure_ascii=False) + "\n")
        meta = {"embedder": self.embedder_name, "n_lemmas": len(self.lemmas),
                "dim": int(self.vectors.shape[1]) if len(self.vectors) else 0,
                "built_at": datetime.now(timezone.utc).isoformat()}
        (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, directory: str | Path) -> "VectorIndex":
        d = Path(directory)
        if not (d / "vectors.npy").exists():
            raise FileNotFoundError(f"No hay índice en {d}. Ejecuta primero: python -m retrieval.build_index")
        vectors = np.load(d / "vectors.npy")
        with open(d / "lemmas.jsonl", encoding="utf-8") as fh:
            lemmas = [json.loads(line) for line in fh if line.strip()]
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        return cls(vectors, lemmas, meta["embedder"])
