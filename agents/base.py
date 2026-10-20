"""Clase base de los agentes que usan LLM: llama, mide y registra (RF-7)."""
from __future__ import annotations

from dataclasses import dataclass

from core.llm_client import BaseLLM, LLMResponse
from core.run_logger import RunLogger


@dataclass
class StepContext:
    """Datos para el registro: a qué problema/subobjetivo/intento pertenece la llamada."""
    problem_id: str = "?"
    subgoal_id: str | None = None
    attempt: int = 0


class LLMAgent:
    name = "agent"

    def __init__(self, llm: BaseLLM, logger: RunLogger | None = None):
        self.llm = llm
        self.logger = logger

    def ask(self, system: str, user: str) -> LLMResponse:
        return self.llm.complete(system, user)

    def log(self, ctx: StepContext, decision: str, resp: LLMResponse | None = None,
            details: dict | None = None) -> None:
        if not self.logger:
            return
        self.logger.log_agent_step(
            problem_id=ctx.problem_id, agent=self.name, attempt=ctx.attempt,
            subgoal_id=ctx.subgoal_id, decision=decision,
            input_tokens=resp.input_tokens if resp else 0,
            output_tokens=resp.output_tokens if resp else 0,
            latency_s=resp.latency_s if resp else 0.0,
            llm_calls=1 if resp else 0,
            details=details)


def format_lemmas(lemmas: list[dict]) -> str:
    if not lemmas:
        return "(none)"
    return "\n".join(f"- {l['name']} : {l['statement']}" for l in lemmas)


def format_feedback(feedback: str | None) -> str:
    return f"\nFeedback from the previous attempt:\n{feedback}\n" if feedback else ""
