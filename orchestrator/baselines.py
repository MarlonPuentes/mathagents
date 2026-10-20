"""Líneas base de agente único (sección 8.2 del PDF).

- Línea base A: un LLM escribe la prueba Lean directamente; Lean la verifica.
  `attempts` > 1 permite medir pass@k con intentos INDEPENDIENTES (sin feedback).
- Línea base B: un LLM razona en lenguaje natural (chain-of-thought) SIN
  verificación formal. Su "resuelto" es solo su AUTOEVALUACIÓN y se marca
  verified_by_lean=False. Para medir "falsos positivos evitados" se puede
  formalizar su respuesta y pasarla por Lean (check_with_lean=True).
"""
from __future__ import annotations

import re
import time

from agents.autoformalizer import Autoformalizer
from agents.base import StepContext
from agents.verifier import LeanVerifier
from core import prompts
from core.llm_client import BaseLLM
from core.run_logger import RunLogger
from core.text_utils import extract_tactics, strip_proof


def _log(logger, pid, agent, attempt, decision, resp=None, details=None):
    if logger:
        logger.log_agent_step(problem_id=pid, agent=agent, attempt=attempt, decision=decision,
                              input_tokens=resp.input_tokens if resp else 0,
                              output_tokens=resp.output_tokens if resp else 0,
                              latency_s=resp.latency_s if resp else 0.0,
                              llm_calls=1 if resp else 0, details=details)


def run_baseline_a(problem: dict, llm: BaseLLM, verifier: LeanVerifier, attempts: int = 1,
                   logger: RunLogger | None = None) -> dict:
    start, calls0 = time.perf_counter(), llm.calls
    tin0, tout0 = llm.total_input_tokens, llm.total_output_tokens
    decl = strip_proof(problem["formal_statement"])
    per_attempt, final_code, cats = [], None, []
    for k in range(attempts):
        resp = llm.complete(prompts.BASELINE_A_SYSTEM,
                            prompts.BASELINE_A_USER.format(informal=problem["informal_statement"], formal=decl))
        tactics = extract_tactics(resp.text)
        if not tactics:
            ok, errors = False, ["No se encontraron tácticas en la respuesta"]
            cats.append("formalization_failure")
        else:
            ver = verifier.verify(decl, tactics)
            ok, errors = ver["verdict"] == "accepted", ver["errors"]
            if ok:
                final_code = ver["lean_code"]
            else:
                from agents.critic import classify_error
                cats.append(classify_error(errors, ver.get("category_hint")))
        per_attempt.append(ok)
        _log(logger, problem["id"], "baseline_a", k, "accepted" if ok else "rejected", resp,
             {"errors": errors[:2]})
    solved_first = per_attempt[0]
    result = {
        "problem_id": problem["id"], "configuration": "baseline_a",
        "solved": solved_first, "verified_by_lean": solved_first,
        "attempt_results": per_attempt, "n_correct": sum(per_attempt), "n_attempts": attempts,
        "status": "solved" if solved_first else "failed",
        "llm_calls": llm.calls - calls0, "input_tokens": llm.total_input_tokens - tin0,
        "output_tokens": llm.total_output_tokens - tout0, "lean_calls": attempts,
        "error_categories": cats, "wall_time_s": round(time.perf_counter() - start, 3),
        "final_lean_code": final_code,
    }
    if logger:
        logger.log_problem_result(result)
    return result


_SELF = re.compile(r"SELF-ASSESSMENT:\s*(CORRECT|INCORRECT)", re.IGNORECASE)


def run_baseline_b(problem: dict, llm: BaseLLM, verifier: LeanVerifier | None = None,
                   check_with_lean: bool = False, logger: RunLogger | None = None) -> dict:
    start, calls0 = time.perf_counter(), llm.calls
    tin0, tout0 = llm.total_input_tokens, llm.total_output_tokens
    resp = llm.complete(prompts.BASELINE_B_SYSTEM, prompts.BASELINE_B_USER.format(informal=problem["informal_statement"]))
    m = _SELF.search(resp.text)
    self_correct = bool(m and m.group(1).upper() == "CORRECT")
    _log(logger, problem["id"], "baseline_b", 0, f"self_assessed_{'correct' if self_correct else 'incorrect'}", resp)

    lean_verdict = None
    if check_with_lean:
        if verifier is None:
            raise ValueError("check_with_lean=True requiere un verificador")
        decl = strip_proof(problem["formal_statement"])
        form = Autoformalizer(llm, logger).formalize(
            {"id": "main", "lean_decl": decl, "informal": problem["informal_statement"]},
            resp.text, [], [], StepContext(problem["id"], "main", 0))
        if form["status"] == "ok":
            lean_verdict = verifier.verify(decl, form["tactics"])["verdict"]
        else:
            lean_verdict = "formalization_failure"
    result = {
        "problem_id": problem["id"], "configuration": "baseline_b",
        "solved": False,                      # nunca cuenta como resuelto: no hay verificación formal
        "verified_by_lean": lean_verdict == "accepted",
        "self_assessed_correct": self_correct,  # SOLUCIÓN GENERADA, NO VERIFICADA
        "lean_check_of_self_assessed": lean_verdict,
        "false_positive_caught": bool(self_correct and lean_verdict not in (None, "accepted")),
        "status": "unverified",
        "llm_calls": llm.calls - calls0, "input_tokens": llm.total_input_tokens - tin0,
        "output_tokens": llm.total_output_tokens - tout0,
        "wall_time_s": round(time.perf_counter() - start, 3),
        "natural_language_proof": resp.text,
    }
    if logger:
        logger.log_problem_result(result)
    return result
