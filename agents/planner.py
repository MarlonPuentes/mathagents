"""Agente Planificador (RF-1): descompone el problema en subobjetivos.

Salida: lista ordenada de subobjetivos. El ÚLTIMO siempre es el teorema
original (is_main=True), que se demuestra al final usando los lemas ya
verificados. Si el LLM responde algo inservible, se usa un plan de respaldo
con solo el teorema original (y se registra esa decisión).
"""
from __future__ import annotations

import re

from agents.base import LLMAgent, StepContext, format_feedback
from core import prompts
from core.schemas import validate
from core.text_utils import extract_json, strip_proof


class Planner(LLMAgent):
    name = "planner"

    def __init__(self, llm, logger=None, max_subgoals: int = 3):
        super().__init__(llm, logger)
        self.max_subgoals = max_subgoals

    def plan(self, problem: dict, ctx: StepContext, feedback: str | None = None) -> dict:
        validate("problem", problem)
        main_decl = strip_proof(problem["formal_statement"])
        system = prompts.PLANNER_SYSTEM.format(max_subgoals=self.max_subgoals)
        user = prompts.PLANNER_USER.format(informal=problem["informal_statement"], formal=main_decl,
                                           feedback=format_feedback(feedback))
        resp = self.ask(system, user)
        subgoals, decision = self._parse(resp.text)
        subgoals.append({"id": "main", "informal": problem["informal_statement"],
                         "lean_decl": main_decl, "is_main": True})
        out = validate("planner_output", {"subgoals": subgoals})
        self.log(ctx, decision, resp, {"n_subgoals": len(subgoals) - 1,
                                       "subgoals": [s["lean_decl"] for s in subgoals]})
        return out

    def _parse(self, text: str) -> tuple[list[dict], str]:
        data = extract_json(text)
        if not isinstance(data, dict) or not isinstance(data.get("subgoals"), list):
            return [], "fallback_single_goal(unparseable)"
        subgoals = []
        for raw in data["subgoals"][: self.max_subgoals]:
            if not isinstance(raw, dict):
                continue
            decl = str(raw.get("lean_decl", "")).strip()
            decl = strip_proof(decl)
            if not re.match(r"^(theorem|lemma)\s+\S+", decl):
                continue
            idx = len(subgoals) + 1
            # Renombra para garantizar nombres únicos y predecibles: subgoal_1, subgoal_2...
            decl = re.sub(r"^(theorem|lemma)\s+\S+", f"theorem subgoal_{idx}", decl, count=1)
            subgoals.append({"id": f"sg{idx}", "informal": str(raw.get("informal", "")),
                             "lean_decl": decl, "is_main": False})
        return subgoals, f"planned_{len(subgoals)}_subgoals"
