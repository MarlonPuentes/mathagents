"""Agente Generador (RF-3): boceto de prueba en lenguaje natural.

Self-consistency (opcional, `n_samples > 1`): se piden varios bocetos y se
elige el que más se parece al resto (el "consenso"). Cada muestra extra es
una llamada LLM más, por eso por defecto n_samples = 1 (RNF-3).
"""
from __future__ import annotations

import re

from agents.base import LLMAgent, StepContext, format_feedback, format_lemmas
from core import prompts
from core.schemas import validate


def _words(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_.']+", text.lower()))


def pick_consensus(candidates: list[str]) -> str:
    """Elige el candidato con mayor similitud promedio (Jaccard) con los demás."""
    if len(candidates) == 1:
        return candidates[0]
    sets = [_words(c) for c in candidates]

    def avg_sim(i: int) -> float:
        sims = [len(sets[i] & sets[j]) / max(1, len(sets[i] | sets[j]))
                for j in range(len(sets)) if j != i]
        return sum(sims) / len(sims)

    best = max(range(len(candidates)), key=avg_sim)
    return candidates[best]


class Generator(LLMAgent):
    name = "generator"

    def __init__(self, llm, logger=None, n_samples: int = 1):
        super().__init__(llm, logger)
        self.n_samples = max(1, n_samples)

    def generate(self, subgoal: dict, lemmas: list[dict], ctx: StepContext,
                 feedback: str | None = None) -> dict:
        user = prompts.GENERATOR_USER.format(goal=subgoal["lean_decl"], informal=subgoal.get("informal", ""),
                                             lemmas=format_lemmas(lemmas), feedback=format_feedback(feedback))
        candidates = []
        for _ in range(self.n_samples):
            resp = self.ask(prompts.GENERATOR_SYSTEM, user)
            candidates.append(resp.text.strip())
            self.log(ctx, "sketch_generated", resp, {"chars": len(resp.text)})
        sketch = pick_consensus(candidates)
        return validate("generator_output", {"sketch": sketch, "candidates": candidates})
