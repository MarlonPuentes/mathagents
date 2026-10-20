"""Ejecuta UNA configuración sobre un split del dataset y guarda resultados + logs.

Ejemplos:
    python -m experiments.run_experiment --configuration full --split dev --limit 2   # corrida de humo
    python -m experiments.run_experiment --configuration baseline_a --split test --attempts 4
    python -m experiments.run_experiment --configuration full --split test --resume results/full_test_XXXX.jsonl

Salida:
    logs/<run_id>.jsonl      -> manifiesto + un evento por agente e intento (RNF-5)
    results/<run_id>.jsonl   -> una línea por problema (la usa experiments.analyze)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from agents.verifier import LeanVerifier
from core.config import build_manifest, load_config, resolve_path, set_global_seed
from core.llm_client import LLMError, create_llm
from core.run_logger import RunLogger
from core.schemas import ContractError, validate
from orchestrator.baselines import run_baseline_a, run_baseline_b
from orchestrator.pipeline import CONFIGURATIONS, build_orchestrator


def load_problems(split: str) -> list[dict]:
    path = resolve_path(f"data/problems_{split}.jsonl") if split != "reference" \
        else resolve_path("data/reference_trivial.jsonl")
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}. Ejecuta primero data/curate_dataset.py")
    with open(path, encoding="utf-8") as fh:
        problems = [json.loads(l) for l in fh if l.strip()]
    for p in problems:
        validate("problem", p)
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configuration", required=True, choices=CONFIGURATIONS)
    ap.add_argument("--split", default="dev", choices=["dev", "test", "reference"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--attempts", type=int, default=1, help="intentos independientes (pass@k) en baseline_a")
    ap.add_argument("--check-baseline-b-with-lean", action="store_true")
    ap.add_argument("--config", default=None)
    ap.add_argument("--resume", default=None, help="archivo results/*.jsonl de una corrida interrumpida")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    set_global_seed(cfg["seed"])
    if cfg["llm"]["provider"] == "mock":
        print("ERROR: provider=mock solo sirve para pruebas. Configura un LLM real en config.yaml "
              "(o usa experiments.smoke_test para probar la tubería).", file=sys.stderr)
        return 2
    problems = load_problems(args.split)[: args.limit]

    if args.resume:
        results_path = Path(args.resume)
        run_id = results_path.stem
        done = {json.loads(l)["problem_id"] for l in open(results_path, encoding="utf-8") if l.strip()}
    else:
        run_id = f"{args.configuration}_{args.split}_{datetime.now():%Y%m%d_%H%M%S}"
        results_path = resolve_path(cfg["paths"]["results_dir"]) / f"{run_id}.jsonl"
        done = set()
    results_path.parent.mkdir(parents=True, exist_ok=True)
    logger = RunLogger(resolve_path(cfg["paths"]["logs_dir"]) / f"{run_id}.jsonl")
    if not args.resume:
        manifest = build_manifest(cfg, args.configuration)
        manifest.update(split=args.split, n_problems=len(problems), attempts=args.attempts)
        logger.log_manifest(manifest)

    try:
        llm = create_llm(cfg)
        verifier = LeanVerifier.from_config(cfg)
        orchestrator = None
        if args.configuration not in ("baseline_a", "baseline_b"):
            orchestrator = build_orchestrator(args.configuration, cfg, llm, verifier, logger)
    except (LLMError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR al preparar el sistema: {exc}", file=sys.stderr)
        return 1

    for i, problem in enumerate(problems, 1):
        if problem["id"] in done:
            continue
        print(f"[{i}/{len(problems)}] {problem['id']} ...", flush=True)
        try:
            if args.configuration == "baseline_a":
                res = run_baseline_a(problem, llm, verifier, args.attempts, logger)
            elif args.configuration == "baseline_b":
                res = run_baseline_b(problem, llm, verifier, args.check_baseline_b_with_lean, logger)
            else:
                res = orchestrator.solve(problem, args.configuration)
        except (LLMError, ContractError) as exc:
            res = {"problem_id": problem["id"], "configuration": args.configuration, "solved": False,
                   "verified_by_lean": False, "status": "error", "failure_reason": str(exc)[:500]}
        res.update(area=problem.get("area"), difficulty=problem.get("difficulty"), run_id=run_id)
        with open(results_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(res, ensure_ascii=False) + "\n")
        label = "VERIFICADO POR LEAN" if res.get("verified_by_lean") and res.get("solved") else \
            ("NO VERIFICADO (autoevaluación del LLM)" if args.configuration == "baseline_b" else "no resuelto")
        print(f"    -> {label} | llamadas LLM: {res.get('llm_calls', '?')}")
    print(f"Resultados: {results_path}\nLog: {logger.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
