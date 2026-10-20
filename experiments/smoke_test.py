"""Prueba de integración de la TUBERÍA con teoremas triviales (propuesta de sección 6.5).

Usa un LLM SIMULADO que siempre responde con tácticas genéricas
(norm_num / linarith / ring / omega) y Lean REAL. Sirve para comprobar que
todos los agentes, el grafo, el verificador y los logs funcionan juntos
ANTES de gastar llamadas en un LLM real.

IMPORTANTE: esto NO mide la capacidad de ningún modelo. Sus resultados no van
al informe como resultados experimentales.

    python -m experiments.smoke_test
"""
from __future__ import annotations

import json
import sys

from agents.verifier import LeanNotFoundError, LeanVerifier
from core.config import load_config, resolve_path
from core.llm_client import MockLLM
from core.prompts import CRITIC_SYSTEM, FORMALIZER_SYSTEM, GENERATOR_SYSTEM
from core.run_logger import RunLogger
from orchestrator.pipeline import build_orchestrator
from retrieval.embedder import HashingEmbedder, lemma_to_text
from retrieval.vector_index import VectorIndex
from agents.retriever import Retriever

GENERIC_TACTICS = "first\n  | omega\n  | linarith\n  | ring\n  | norm_num"


def scripted_llm() -> MockLLM:
    def respond(system: str, user: str) -> str:
        if system.startswith("You are the Planner"):
            return '{"reasoning": "simple goal", "subgoals": []}'
        if system == GENERATOR_SYSTEM:
            return "Direct computation / linear arithmetic closes the goal."
        if system == FORMALIZER_SYSTEM:
            return f"```lean\n{GENERIC_TACTICS}\n```"
        if system == CRITIC_SYSTEM:
            return '{"action": "abandon", "error_category": "other", "advice": "smoke test"}'
        return "unused"
    return MockLLM(respond, model="scripted-smoke-mock")


def main() -> int:
    cfg = load_config(overrides={"retrieval.embedder": "hashing"})
    try:
        verifier = LeanVerifier.from_config(cfg)
    except (LeanNotFoundError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    corpus = [{"name": "add_comm", "statement": "∀ a b, a + b = b + a", "module": "demo"},
              {"name": "two_mul", "statement": "2 * n = n + n", "module": "demo"}]
    emb = HashingEmbedder()
    log_path = resolve_path("logs/smoke_test.jsonl")
    log_path.unlink(missing_ok=True)  # cada ejecución empieza un log limpio
    logger = RunLogger(log_path)
    retriever = Retriever(VectorIndex.build(corpus, emb, lemma_to_text), emb, top_k=2, logger=logger)
    orch = build_orchestrator("full", cfg, scripted_llm(), verifier, logger, retriever)
    with open(resolve_path("data/reference_trivial.jsonl"), encoding="utf-8") as fh:
        problems = [json.loads(l) for l in fh if l.strip()]
    ok = 0
    for p in problems:
        r = orch.solve(p, "smoke")
        ok += r["solved"]
        print(f"{p['id']:12s} -> {'VERIFICADO POR LEAN' if r['solved'] else 'NO resuelto: ' + str(r['failure_reason'])}"
              f" | llamadas LLM simuladas: {r['llm_calls']}")
    print(f"\n{ok}/{len(problems)} teoremas triviales verificados. Log: logs/smoke_test.jsonl")
    return 0 if ok == len(problems) else 1


if __name__ == "__main__":
    sys.exit(main())
