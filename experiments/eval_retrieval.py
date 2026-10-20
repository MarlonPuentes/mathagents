"""Calidad del Recuperador ANTES de integrarlo (riesgo "RAG irrelevante" de la sección 11 del PDF).

Usa data/retrieval_reference.jsonl: pares (consulta en lenguaje natural, lema esperado).
Mide recall@k = proporción de consultas cuyo lema esperado aparece entre los k primeros.

    python -m experiments.eval_retrieval --k 1 5 10
"""
from __future__ import annotations

import argparse
import json
import sys

from core.config import load_config, resolve_path
from retrieval.embedder import create_embedder
from retrieval.vector_index import VectorIndex


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, nargs="+", default=[1, 5, 10])
    ap.add_argument("--index-dir", default=None)
    ap.add_argument("--embedder", default=None, help="hashing | sentence_transformers (por defecto: config)")
    args = ap.parse_args(argv)
    overrides = {"retrieval.embedder": args.embedder} if args.embedder else {}
    cfg = load_config(overrides=overrides)
    index = VectorIndex.load(args.index_dir or resolve_path(cfg["retrieval"]["index_dir"]))
    embedder = create_embedder(cfg)
    if embedder.name != index.embedder_name:
        print(f"ERROR: índice hecho con {index.embedder_name}, embedder actual {embedder.name}", file=sys.stderr)
        return 1
    names = {l["name"] for l in index.lemmas}
    rows = [json.loads(l) for l in open(resolve_path("data/retrieval_reference.jsonl"), encoding="utf-8") if l.strip()]
    rows = [r for r in rows if r["expected"] in names]  # solo lemas presentes en el corpus
    if not rows:
        print("Ningún lema esperado está en el índice", file=sys.stderr)
        return 1
    kmax = max(args.k)
    hits = {k: 0 for k in args.k}
    for r in rows:
        top = [index.lemmas[i]["name"] for i, _ in index.search(embedder.encode([r["query"]])[0], kmax)]
        for k in args.k:
            hits[k] += r["expected"] in top[:k]
        print(f"{r['expected']:18s} rank={top.index(r['expected']) + 1 if r['expected'] in top else '>' + str(kmax)}")
    print(f"\nEmbedder: {embedder.name} | corpus: {len(index.lemmas)} lemas | consultas: {len(rows)}")
    for k in args.k:
        print(f"recall@{k} = {hits[k]}/{len(rows)} = {hits[k] / len(rows):.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
