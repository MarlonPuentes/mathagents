"""Construye el índice vectorial a partir del JSONL extraído de Mathlib.

Paso 1 (Lean, una vez):
    cd lean_project
    lake env lean --run scripts/ExtractDecls.lean Mathlib ../retrieval/mathlib_decls.jsonl Mathlib.Algebra Mathlib.NumberTheory Mathlib.Combinatorics Mathlib.Data.Nat Mathlib.Data.Int Mathlib.Data.Real Mathlib.Tactic
Paso 2 (Python):
    python -m retrieval.build_index --decls retrieval/mathlib_decls.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.config import load_config, resolve_path, set_global_seed
from retrieval.embedder import create_embedder, lemma_to_text
from retrieval.vector_index import VectorIndex


def load_decls(path: Path, limit: int | None = None) -> list[dict]:
    decls = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("name") and d.get("statement"):
                decls.append({"name": d["name"], "statement": d["statement"], "module": d.get("module")})
            if limit and len(decls) >= limit:
                break
    return decls


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Construye el índice de embeddings de Mathlib")
    ap.add_argument("--decls", required=True, help="JSONL generado por ExtractDecls.lean")
    ap.add_argument("--config", default=None)
    ap.add_argument("--limit", type=int, default=None, help="solo los primeros N (para pruebas)")
    ap.add_argument("--out", default=None, help="carpeta de salida (por defecto retrieval.index_dir)")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    set_global_seed(cfg["seed"])
    decls_path = Path(args.decls)
    if not decls_path.exists():
        print(f"ERROR: no existe {decls_path}", file=sys.stderr)
        return 1
    decls = load_decls(decls_path, args.limit)
    if not decls:
        print("ERROR: el archivo no contiene declaraciones", file=sys.stderr)
        return 1
    print(f"Calculando embeddings de {len(decls)} lemas con '{cfg['retrieval']['embedder']}'...")
    index = VectorIndex.build(decls, create_embedder(cfg), lemma_to_text)
    out_dir = Path(args.out) if args.out else resolve_path(cfg["retrieval"]["index_dir"])
    index.save(out_dir)
    print(f"Índice guardado en {out_dir} ({len(decls)} lemas, dim={index.vectors.shape[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
