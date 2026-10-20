"""LLM simulado por agente para las pruebas: cada agente tiene su propia cola de respuestas."""
from core import prompts
from core.llm_client import MockLLM


def agent_of(system: str) -> str:
    if system.startswith("You are the Planner"):
        return "planner"
    return {prompts.GENERATOR_SYSTEM: "generator", prompts.FORMALIZER_SYSTEM: "formalizer",
            prompts.CRITIC_SYSTEM: "critic", prompts.BASELINE_A_SYSTEM: "baseline_a",
            prompts.BASELINE_B_SYSTEM: "baseline_b"}.get(system, "unknown")


def scripted(**queues) -> MockLLM:
    """scripted(planner=[...], generator=[...], formalizer=[...], critic=[...]).

    Si la cola de un agente se vacía, se repite su última respuesta.
    """
    queues = {k: list(v) for k, v in queues.items()}
    last = {}

    def respond(system, user):
        who = agent_of(system)
        q = queues.get(who)
        if q:
            last[who] = q.pop(0)
        if who not in last:
            raise AssertionError(f"El agente '{who}' no tiene respuestas simuladas")
        return last[who]
    return MockLLM(respond)


def lean(tactics: str) -> str:
    return f"```lean\n{tactics}\n```"
