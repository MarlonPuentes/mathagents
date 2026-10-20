"""Agente Crítico/Refinador (RF-6): lee el error de Lean y decide qué hacer.

Combina reglas fijas + LLM:
1. Reglas (sin costo): clasifican el error por patrones del mensaje de Lean
   y hacen cumplir los límites k_max y max_replans.
2. LLM (opcional): da un consejo concreto de corrección (Self-Refine) y
   propone una acción. Si su respuesta no sirve, mandan las reglas.
"""
from __future__ import annotations

import json
import re

from agents.base import LLMAgent, StepContext
from core import prompts
from core.schemas import ERROR_CATEGORIES, validate
from core.text_utils import extract_json

_RULES = [
    (r"unknown (identifier|constant)|unknown namespace", "missing_lemma"),
    (r"unexpected token|expected term|unterminated|invalid syntax|expected '", "lean_syntax"),
    (r"timeout|maxHeartbeats|Tiempo límite", "timeout"),
    (r"Construcción prohibida|axiomas no permitidos|usa 'sorry'", "other"),
    (r"type mismatch|failed to synthesize|could not prove|linarith failed|unsolved goals|omega could not", "misformalization"),
]


def classify_error(errors: list[str], hint: str | None = None) -> str:
    if hint in ERROR_CATEGORIES:
        return hint
    text = "\n".join(errors)
    for pattern, category in _RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return category
    return "other"


class Critic(LLMAgent):
    name = "critic"

    def __init__(self, llm, logger=None, k_max: int = 3, max_replans: int = 1, use_llm: bool = True):
        super().__init__(llm, logger)
        self.k_max = k_max
        self.max_replans = max_replans
        self.use_llm = use_llm

    def critique(self, subgoal: dict, errors: list[str], tactics: str | None, attempt: int,
                 replans_done: int, history: list[dict], ctx: StepContext,
                 hint: str | None = None, allow_llm: bool = True) -> dict:
        category = classify_error(errors, hint)
        can_retry = attempt < self.k_max
        can_replan = replans_done < self.max_replans

        # Regla 1: el enunciado del subobjetivo no compila -> es culpa del plan.
        # (Si es el teorema oficial del dataset, replanificar no sirve: se abandona.)
        if category == "planning_error":
            action = "replan" if can_replan and not subgoal.get("is_main") else "abandon"
            return self._finish(ctx, action, category, "The subgoal statement itself does not compile.", None)
        # Regla 2: se acabaron los reintentos.
        if not can_retry:
            action = "replan" if can_replan else "abandon"
            return self._finish(ctx, action, category, f"k_max={self.k_max} attempts exhausted.", None)

        advice, action, resp = "Fix the Lean error and try again.", "retry", None
        if self.use_llm and allow_llm:
            user = prompts.CRITIC_USER.format(goal=subgoal["lean_decl"], attempt=attempt, k_max=self.k_max,
                                              errors="\n".join(errors)[:3000], tactics=tactics or "(none)",
                                              history=json.dumps(history[-3:], ensure_ascii=False)[:2000])
            resp = self.ask(prompts.CRITIC_SYSTEM, user)
            data = extract_json(resp.text)
            if isinstance(data, dict):
                advice = str(data.get("advice") or advice)[:1000]
                proposed = data.get("action")
                if proposed == "replan" and can_replan:
                    action = "replan"
                elif proposed == "abandon":
                    action = "abandon"
                if data.get("error_category") in ERROR_CATEGORIES and category == "other":
                    category = data["error_category"]
        return self._finish(ctx, action, category, advice, resp)

    def _finish(self, ctx: StepContext, action: str, category: str, advice: str, resp) -> dict:
        out = validate("critic_output", {"action": action, "error_category": category, "advice": advice})
        self.log(ctx, action, resp, {"error_category": category, "advice": advice})
        return out
