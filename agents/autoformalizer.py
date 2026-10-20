"""Agente Autoformalizador (RF-4): boceto en lenguaje natural -> tácticas Lean 4.

Devuelve {"status": "ok", "tactics": ...} o
         {"status": "formalization_failure", "reason": ...}.
Nunca devuelve "nada": si el LLM no produce algo usable, se reporta el fallo
de forma explícita, como exige RF-4.
"""
from __future__ import annotations

from agents.base import LLMAgent, StepContext, format_feedback, format_lemmas
from core import prompts
from core.schemas import validate
from core.text_utils import brackets_balanced, extract_tactics


class Autoformalizer(LLMAgent):
    name = "autoformalizer"

    def formalize(self, subgoal: dict, sketch: str, lemmas: list[dict], context_lemmas: list[str],
                  ctx: StepContext, feedback: str | None = None) -> dict:
        context = "\n".join(c.split(":= by")[0].strip() for c in context_lemmas) or "(none)"
        user = prompts.FORMALIZER_USER.format(goal=subgoal["lean_decl"], context=context,
                                              lemmas=format_lemmas(lemmas), sketch=sketch,
                                              feedback=format_feedback(feedback))
        resp = self.ask(prompts.FORMALIZER_SYSTEM, user)
        result = self._parse(resp.text)
        self.log(ctx, result["status"], resp, {"tactics": result.get("tactics"),
                                               "reason": result.get("reason")})
        return validate("autoformalizer_output", result)

    @staticmethod
    def _parse(text: str) -> dict:
        if "FORMALIZATION_FAILURE" in text:
            reason = text.split("FORMALIZATION_FAILURE", 1)[1].lstrip(": ").strip() or "sin motivo"
            return {"status": "formalization_failure", "reason": reason[:500]}
        tactics = extract_tactics(text)
        if not tactics:
            return {"status": "formalization_failure", "reason": "No se encontró un bloque de tácticas Lean"}
        if not brackets_balanced(tactics):
            return {"status": "formalization_failure", "reason": "Paréntesis/corchetes desbalanceados"}
        return {"status": "ok", "tactics": tactics}
