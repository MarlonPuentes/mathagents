"""Orquestador: grafo de estados con LangGraph (sección 6.1-6.2 del PDF).

Estados: PLAN -> RETRIEVE -> GENERATE -> FORMALIZE -> VERIFY -> (DONE | CRITIQUE)
         CRITIQUE -> GENERATE (reintentar) | PLAN (replanificar) | FAIL (abandonar)
Un subobjetivo aceptado pasa al siguiente (RETRIEVE). El problema solo queda
"solved" cuando Lean acepta el teorema principal (RNF-1): ese es el ÚNICO lugar
del código que pone solved=True.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.autoformalizer import Autoformalizer
from agents.base import StepContext
from agents.critic import Critic
from agents.generator import Generator
from agents.planner import Planner
from agents.retriever import Retriever
from agents.verifier import LeanVerifier
from core.llm_client import BaseLLM
from core.run_logger import RunLogger


class ProofState(TypedDict, total=False):
    problem: dict
    subgoals: list[dict]
    idx: int                    # subobjetivo actual
    attempt: int                # intentos hechos sobre el subobjetivo actual
    replans: int
    lemmas: list[dict]          # lemas recuperados por RAG para el subobjetivo actual
    sketch: str
    formalization: dict
    verification: dict
    verified_lemmas: list[str]  # código Lean de los subobjetivos ya aceptados
    feedback: str | None        # retroalimentación para el siguiente intento
    replan_feedback: str | None
    history: list[dict]
    status: str                 # running | solved | failed
    failure_reason: str | None
    error_categories: list[str]
    lean_calls: int
    retrieval_calls: int
    final_lean_code: str | None
    critic_action: str


@dataclass
class PipelineOptions:
    use_rag: bool = True
    use_critic: bool = True
    k_max: int = 3
    max_replans: int = 1
    llm_call_budget: int = 20


class ProofOrchestrator:
    def __init__(self, llm: BaseLLM, verifier: LeanVerifier, retriever: Retriever | None,
                 options: PipelineOptions, logger: RunLogger | None = None,
                 max_subgoals: int = 3, generator_samples: int = 1, critic_uses_llm: bool = True):
        if options.use_rag and retriever is None:
            raise ValueError("use_rag=True requiere un Retriever")
        self.llm = llm
        self.verifier = verifier
        self.retriever = retriever
        self.opt = options
        self.logger = logger
        self.planner = Planner(llm, logger, max_subgoals)
        self.generator = Generator(llm, logger, generator_samples)
        self.formalizer = Autoformalizer(llm, logger)
        self.critic = Critic(llm, logger, k_max=options.k_max, max_replans=options.max_replans,
                             use_llm=critic_uses_llm)
        self.graph = self._build_graph()
        self._calls_at_start = 0

    # ------------------------------------------------------------------ helpers
    def _ctx(self, s: ProofState) -> StepContext:
        sg = s["subgoals"][s["idx"]] if s.get("subgoals") and s.get("idx", 0) < len(s["subgoals"]) else None
        return StepContext(problem_id=s["problem"]["id"], subgoal_id=sg["id"] if sg else None,
                           attempt=s.get("attempt", 0))

    def _calls_used(self) -> int:
        return self.llm.calls - self._calls_at_start

    def _budget_left(self) -> int:
        return self.opt.llm_call_budget - self._calls_used()

    @staticmethod
    def _current(s: ProofState) -> dict:
        return s["subgoals"][s["idx"]]

    # ------------------------------------------------------------------ nodos
    def node_plan(self, s: ProofState) -> dict:
        out = self.planner.plan(s["problem"], self._ctx(s), s.get("replan_feedback"))
        return {"subgoals": out["subgoals"], "idx": 0, "attempt": 0, "verified_lemmas": [],
                "feedback": None, "lemmas": []}

    def node_retrieve(self, s: ProofState) -> dict:
        if not self.opt.use_rag:
            return {"lemmas": []}
        out = self.retriever.retrieve(self._current(s), self._ctx(s))
        return {"lemmas": out["lemmas"], "retrieval_calls": s.get("retrieval_calls", 0) + 1}

    def node_generate(self, s: ProofState) -> dict:
        out = self.generator.generate(self._current(s), s.get("lemmas", []), self._ctx(s), s.get("feedback"))
        return {"sketch": out["sketch"]}

    def node_formalize(self, s: ProofState) -> dict:
        out = self.formalizer.formalize(self._current(s), s["sketch"], s.get("lemmas", []),
                                        s.get("verified_lemmas", []), self._ctx(s), s.get("feedback"))
        return {"formalization": out}

    def node_verify(self, s: ProofState) -> dict:
        sg, form = self._current(s), s["formalization"]
        if form["status"] != "ok":
            ver = {"verdict": "rejected", "errors": [f"Formalization failure: {form.get('reason')}"],
                   "lean_code": "", "duration_s": 0.0, "axioms": [], "category_hint": "formalization_failure"}
            lean_calls = s.get("lean_calls", 0)
        else:
            ver = self.verifier.verify(sg["lean_decl"], form["tactics"], s.get("verified_lemmas", []))
            lean_calls = s.get("lean_calls", 0) + 1
        if self.logger:
            self.logger.log_agent_step(problem_id=s["problem"]["id"], agent="verifier", attempt=s.get("attempt", 0),
                                       subgoal_id=sg["id"], decision=ver["verdict"], latency_s=ver["duration_s"],
                                       details={"errors": ver["errors"][:3], "axioms": ver.get("axioms")})
        update: dict[str, Any] = {"verification": ver, "lean_calls": lean_calls}
        history = list(s.get("history", []))
        history.append({"subgoal": sg["id"], "attempt": s.get("attempt", 0), "verdict": ver["verdict"],
                        "errors": ver["errors"][:2], "tactics": form.get("tactics")})
        update["history"] = history
        if ver["verdict"] == "accepted":
            body = "\n".join("  " + ln if ln.strip() else "" for ln in form["tactics"].splitlines())
            verified = list(s.get("verified_lemmas", [])) + [f"{sg['lean_decl']} := by\n{body}"]
            update.update(verified_lemmas=verified, idx=s["idx"] + 1, attempt=0, feedback=None)
            if sg.get("is_main"):
                update.update(status="solved", final_lean_code=ver["lean_code"])  # ÚNICO lugar (RNF-1)
        return update

    def node_critique(self, s: ProofState) -> dict:
        attempt = s.get("attempt", 0) + 1
        ver = s["verification"]
        ctx = self._ctx(s)
        ctx.attempt = attempt
        result = self.critic.critique(self._current(s), ver["errors"], s["formalization"].get("tactics"),
                                      attempt, s.get("replans", 0), s.get("history", []), ctx,
                                      hint=ver.get("category_hint"), allow_llm=self._budget_left() > 2)
        cats = list(s.get("error_categories", [])) + [result["error_category"]]
        update: dict[str, Any] = {"attempt": attempt, "error_categories": cats}
        errors_text = "\n".join(ver["errors"])[:2000]
        if result["action"] == "retry":
            update["feedback"] = f"Lean error:\n{errors_text}\nCritic advice: {result['advice']}"
        elif result["action"] == "replan":
            update["replans"] = s.get("replans", 0) + 1
            update["replan_feedback"] = (f"The previous plan failed at subgoal '{self._current(s)['lean_decl']}'. "
                                         f"Error: {errors_text[:800]}. Advice: {result['advice']}")
        else:
            update.update(status="failed", failure_reason=f"abandoned ({result['error_category']})")
        update["critic_action"] = result["action"]
        return update

    def node_fail_budget(self, s: ProofState) -> dict:
        return {"status": "failed", "failure_reason": "llm_call_budget_exhausted"}

    def node_fail_no_critic(self, s: ProofState) -> dict:
        cat = s["verification"].get("category_hint") or "other"
        return {"status": "failed", "failure_reason": "rejected_without_critic",
                "error_categories": list(s.get("error_categories", [])) + [cat]}

    # ------------------------------------------------------------------ transiciones
    def _needs_llm(self, target: str) -> str:
        return target if self._budget_left() > 0 else "fail_budget"

    def route_after_verify(self, s: ProofState) -> str:
        if s.get("status") == "solved":
            return END
        if s["verification"]["verdict"] == "accepted":
            return "retrieve"
        return "critique" if self.opt.use_critic else "fail_no_critic"

    def route_after_critique(self, s: ProofState) -> str:
        if s.get("status") == "failed":
            return END
        action = s.get("critic_action")
        return self._needs_llm("plan" if action == "replan" else "generate")

    def _build_graph(self):
        g = StateGraph(ProofState)
        for name, fn in [("plan", self.node_plan), ("retrieve", self.node_retrieve),
                         ("generate", self.node_generate), ("formalize", self.node_formalize),
                         ("verify", self.node_verify), ("critique", self.node_critique),
                         ("fail_budget", self.node_fail_budget), ("fail_no_critic", self.node_fail_no_critic)]:
            g.add_node(name, fn)
        g.add_conditional_edges(START, lambda s: self._needs_llm("plan"), ["plan", "fail_budget"])
        g.add_edge("plan", "retrieve")
        g.add_conditional_edges("retrieve", lambda s: self._needs_llm("generate"), ["generate", "fail_budget"])
        g.add_conditional_edges("generate", lambda s: self._needs_llm("formalize"), ["formalize", "fail_budget"])
        g.add_edge("formalize", "verify")
        g.add_conditional_edges("verify", self.route_after_verify, ["retrieve", "critique", "fail_no_critic", END])
        g.add_conditional_edges("critique", self.route_after_critique, ["plan", "generate", "fail_budget", END])
        g.add_edge("fail_budget", END)
        g.add_edge("fail_no_critic", END)
        return g.compile()

    # ------------------------------------------------------------------ ejecución
    def solve(self, problem: dict, configuration: str = "full") -> dict:
        """Resuelve un problema y devuelve un resumen listo para el análisis."""
        self._calls_at_start = self.llm.calls
        tok_in0, tok_out0 = self.llm.total_input_tokens, self.llm.total_output_tokens
        start = time.perf_counter()
        init: ProofState = {"problem": problem, "status": "running", "replans": 0, "history": [],
                            "error_categories": [], "lean_calls": 0, "retrieval_calls": 0}
        error = None
        try:
            final = self.graph.invoke(init, config={"recursion_limit": 500})
        except Exception as exc:  # un error de programa no debe tumbar todo el experimento
            final, error = dict(init), f"{type(exc).__name__}: {exc}"
        solved = final.get("status") == "solved"
        accepted_attempts = [h["attempt"] for h in final.get("history", []) if h["verdict"] == "accepted"]
        result = {
            "problem_id": problem["id"], "configuration": configuration,
            "solved": solved, "verified_by_lean": solved,
            "status": final.get("status", "failed") if not error else "error",
            "failure_reason": error or final.get("failure_reason"),
            "llm_calls": self._calls_used(),
            "input_tokens": self.llm.total_input_tokens - tok_in0,
            "output_tokens": self.llm.total_output_tokens - tok_out0,
            "lean_calls": final.get("lean_calls", 0),
            "retrieval_calls": final.get("retrieval_calls", 0),
            "replans": final.get("replans", 0),
            "n_subgoals": max(0, len(final.get("subgoals", [])) - 1),
            "attempts": len(final.get("history", [])),
            # Índice del intento más alto que fue necesario (0 = al primer intento). Sirve para
            # estimar la "ganancia por reintento" (sección 8.3). Solo tiene sentido si solved=True.
            "max_attempt_index_used": max(accepted_attempts) if solved and accepted_attempts else None,
            "error_categories": final.get("error_categories", []),
            "wall_time_s": round(time.perf_counter() - start, 3),
            "final_lean_code": final.get("final_lean_code"),
        }
        if self.logger:
            self.logger.log_problem_result(result)
        return result
