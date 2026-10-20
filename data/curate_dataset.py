"""Curación del conjunto de evaluación (sección 8.1 del PDF).

Qué hace:
1. Lee miniF2F en formato JSONL (versión Lean 4 publicada por DeepSeek-Prover-V1.5,
   campos: name, split, informal_prefix, formal_statement, header).
2. Asigna ÁREA y DIFICULTAD con reglas simples y transparentes (ver abajo).
   Lo que las reglas no pueden clasificar queda como "unclassified" y se
   revisa a mano: NO se inventa una etiqueta.
3. Muestra estratificada con semilla fija: dev = split "valid" de miniF2F,
   test = split "test" (disjuntos, evita sobreajustar prompts).
4. (--check-lean) Compila cada enunciado con `sorry` en TU versión de Mathlib
   y descarta los que ya no compilan (miniF2F se escribió con versiones viejas).

Uso:
    python -m data.curate_dataset --input data/raw/minif2f.jsonl --n-dev 15 --n-test 45 --check-lean
Combinatoria: miniF2F casi no tiene; agréguenla desde PutnamBench con --extra
(un JSONL con los mismos campos que produce este script).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/deepseek-ai/DeepSeek-Prover-V1.5/main/datasets/minif2f.jsonl"


def area_of(name: str) -> str:
    if "algebra" in name:
        return "algebra"
    if "numbertheory" in name:
        return "number_theory"
    return "unclassified"  # amc/aime/imo/induction: requieren revisión manual


def difficulty_of(name: str) -> int:
    """1 = MATH (mathd), 2 = AMC / ejercicios de libro, 3 = AIME / IMO."""
    if name.startswith("mathd_"):
        return 1
    if name.startswith(("aime", "imo")):
        return 3
    return 2


def clean_informal(prefix: str) -> str:
    return re.sub(r"^/--\s*|\s*-/\s*$", "", prefix.strip()).strip()


def to_problem(raw: dict) -> dict:
    formal = re.sub(r":=\s*by\s*$", "", raw["formal_statement"].strip()).strip()
    return {
        "id": raw["name"],
        "informal_statement": clean_informal(raw.get("informal_prefix", "")),
        "formal_statement": formal,
        "area": area_of(raw["name"]),
        "difficulty": difficulty_of(raw["name"]),
        "split": "dev" if raw.get("split") == "valid" else "test",
        "source": "miniF2F (Lean 4 version from DeepSeek-Prover-V1.5 repo)",
        "lean_check": "pending",
    }


def stratified_sample(problems: list[dict], n: int, seed: int) -> list[dict]:
    """Reparte n lo más parejo posible entre las celdas (área x dificultad)."""
    rng = random.Random(seed)
    cells: dict[tuple, list[dict]] = defaultdict(list)
    for p in problems:
        if p["area"] != "unclassified":
            cells[(p["area"], p["difficulty"])].append(p)
    for items in cells.values():
        rng.shuffle(items)
    chosen: list[dict] = []
    keys = sorted(cells)
    while len(chosen) < n and any(cells[k] for k in keys):
        for k in keys:
            if cells[k] and len(chosen) < n:
                chosen.append(cells[k].pop())
    return sorted(chosen, key=lambda p: p["id"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help=f"JSONL de miniF2F (descárgalo de {SOURCE_URL})")
    ap.add_argument("--n-dev", type=int, default=15)
    ap.add_argument("--n-test", type=int, default=45)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--extra", default=None, help="JSONL adicional (ej. combinatoria de PutnamBench)")
    ap.add_argument("--check-lean", action="store_true", help="compila cada enunciado con sorry")
    ap.add_argument("--out-dir", default="data")
    args = ap.parse_args(argv)

    path = Path(args.input)
    if not path.exists():
        print(f"ERROR: no existe {path}. Descárgalo de {SOURCE_URL}", file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as fh:
        problems = [to_problem(json.loads(l)) for l in fh if l.strip()]
    if args.extra:
        with open(args.extra, encoding="utf-8") as fh:
            problems += [json.loads(l) for l in fh if l.strip()]

    if args.check_lean:
        from core.config import load_config
        from agents.verifier import LeanVerifier
        verifier = LeanVerifier.from_config(load_config())
        for i, p in enumerate(problems, 1):
            res = verifier.check_statement(p["formal_statement"])
            p["lean_check"] = "ok" if res["compiles"] else "fails"
            p["lean_check_errors"] = res["errors"][:2]
            print(f"[{i}/{len(problems)}] {p['id']}: {p['lean_check']}")
        problems = [p for p in problems if p["lean_check"] == "ok"]

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    unclassified = [p for p in problems if p["area"] == "unclassified"]
    with open(out / "unclassified_for_manual_review.jsonl", "w", encoding="utf-8") as fh:
        for p in unclassified:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    for split, n in [("dev", args.n_dev), ("test", args.n_test)]:
        pool = [p for p in problems if p["split"] == split]
        sample = stratified_sample(pool, n, args.seed)
        with open(out / f"problems_{split}.jsonl", "w", encoding="utf-8") as fh:
            for p in sample:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
        counts = defaultdict(int)
        for p in sample:
            counts[(p["area"], p["difficulty"])] += 1
        print(f"{split}: {len(sample)} problemas -> {dict(sorted(counts.items()))}")
    print(f"{len(unclassified)} problemas sin área automática -> unclassified_for_manual_review.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
