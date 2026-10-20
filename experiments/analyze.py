"""Calcula las métricas de la sección 8.3 a partir de results/*.jsonl.

    python -m experiments.analyze results/full_test_*.jsonl results/no_rag_test_*.jsonl ...

Imprime una tabla por configuración y las comparaciones pareadas (McNemar +
Bonferroni). Solo usa datos reales de los archivos: si falta una
configuración, simplemente no aparece.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from experiments.stats import (bonferroni, bootstrap_mean_ci, mcnemar_exact, median_iqr,
                               pass_at_k, wilson_interval)


def load_results(paths: list[str]) -> dict[str, list[dict]]:
    by_config: dict[str, list[dict]] = defaultdict(list)
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    by_config[r["configuration"]].append(r)
    return by_config


def is_verified_success(r: dict) -> bool:
    """RNF-1: solo cuenta lo que Lean aceptó."""
    return bool(r.get("solved") and r.get("verified_by_lean"))


def summarize(config: str, rows: list[dict], k_values=(1, 2, 4)) -> dict:
    n = len(rows)
    s = {"configuration": config, "n": n}
    if config == "baseline_b":
        self_ok = sum(1 for r in rows if r.get("self_assessed_correct"))
        checked = [r for r in rows if r.get("lean_check_of_self_assessed") is not None and r.get("self_assessed_correct")]
        s.update(self_assessed_correct=self_ok,
                 self_assessed_checked_with_lean=len(checked),
                 false_positives_caught=sum(1 for r in checked if r.get("false_positive_caught")))
        return s
    succ = sum(1 for r in rows if is_verified_success(r))
    lo, hi = wilson_interval(succ, n) if n else (0, 0)
    s.update(solved=succ, pass1=succ / n if n else 0.0, pass1_ci95=(lo, hi))
    if config == "baseline_a" and rows and "n_attempts" in rows[0]:
        att = rows[0]["n_attempts"]
        s["pass_at_k"] = {k: sum(pass_at_k(att, r["n_correct"], k) for r in rows) / n
                          for k in k_values if k <= att}
    solved_rows = [r for r in rows if is_verified_success(r)]
    calls = [r.get("llm_calls", 0) for r in solved_rows]
    if calls:
        mean, clo, chi = bootstrap_mean_ci(calls)
        s["llm_calls_per_solved"] = {"mean": mean, "ci95": (clo, chi), "median_iqr": median_iqr(calls),
                                     "rnf3_ok(<=20)": mean <= 20}
    for key in ["input_tokens", "output_tokens", "wall_time_s", "retrieval_calls", "lean_calls"]:
        vals = [r.get(key, 0) or 0 for r in solved_rows]
        if vals:
            s[f"{key}_per_solved_median_iqr"] = median_iqr(vals)
    s["error_taxonomy"] = dict(Counter(c for r in rows for c in r.get("error_categories", [])))
    idx = [r["max_attempt_index_used"] for r in solved_rows if r.get("max_attempt_index_used") is not None]
    if idx:
        # Tasa de éxito si solo se hubieran permitido j intentos (aprox.: ignora replanificación)
        s["success_if_k_max"] = {j: sum(1 for i in idx if i < j) / n for j in range(1, max(idx) + 2)}
    return s


def paired_comparisons(by_config: dict[str, list[dict]]) -> list[dict]:
    configs = [c for c in by_config if c != "baseline_b"]
    raw = []
    for a, b in combinations(sorted(configs), 2):
        ra = {r["problem_id"]: is_verified_success(r) for r in by_config[a]}
        rb = {r["problem_id"]: is_verified_success(r) for r in by_config[b]}
        common = sorted(set(ra) & set(rb))
        if not common:
            continue
        res = mcnemar_exact([ra[p] for p in common], [rb[p] for p in common])
        raw.append({"a": a, "b": b, "n_common": len(common), **res})
    adj = bonferroni([c["p_value"] for c in raw], n_comparisons=len(raw))
    for c, p in zip(raw, adj):
        c["p_bonferroni"] = p
        c["significant_at_0.05"] = p < 0.05
    return raw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--out", default=None, help="guardar el resumen en JSON")
    args = ap.parse_args(argv)
    missing = [p for p in args.results if not Path(p).exists()]
    if missing:
        print(f"ERROR: no existen {missing}", file=sys.stderr)
        return 1
    by_config = load_results(args.results)
    summary = {"per_configuration": [summarize(c, rows) for c, rows in sorted(by_config.items())],
               "paired_mcnemar": paired_comparisons(by_config)}
    if "full" in by_config and "no_rag" in by_config:
        f = next(s for s in summary["per_configuration"] if s["configuration"] == "full")
        nr = next(s for s in summary["per_configuration"] if s["configuration"] == "no_rag")
        summary["rag_contribution_pass1"] = f["pass1"] - nr["pass1"]
    text = json.dumps(summary, indent=2, ensure_ascii=False, default=str)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
