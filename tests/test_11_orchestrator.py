"""Paso 11: orquestador LangGraph completo, con LLM simulado y Lean REAL.

Cada prueba recorre un camino distinto de la máquina de estados (sección 6.2).
"""
import pytest

from agents.retriever import Retriever
from helpers import lean, scripted
from orchestrator.pipeline import build_orchestrator
from retrieval.embedder import HashingEmbedder, lemma_to_text
from retrieval.vector_index import VectorIndex

PROBLEM = {"id": "o1", "informal_statement": "If x + 3 = 5 then 2x = 4.",
           "formal_statement": "theorem o1 (x : ℚ) (h₀ : x + 3 = 5) : 2 * x = 4", "area": "algebra", "difficulty": 0}
NO_PLAN = '{"subgoals": []}'
ONE_SUBGOAL = '{"subgoals": [{"informal": "x = 2", "lean_decl": "theorem s (x : ℚ) (h₀ : x + 3 = 5) : x = 2"}]}'
RETRY = '{"action": "retry", "error_category": "misformalization", "advice": "use linarith"}'


@pytest.fixture
def retriever():
    e = HashingEmbedder()
    corpus = [{"name": "two_mul", "statement": "2 * n = n + n", "module": "m"}]
    return Retriever(VectorIndex.build(corpus, e, lemma_to_text), e, top_k=1)


def make(cfg, verifier, retriever, configuration="full", **queues):
    llm = scripted(**queues)
    return build_orchestrator(configuration, cfg, llm, verifier, None, retriever), llm


def test_direct_proof_is_solved(cfg, verifier, retriever):
    orch, llm = make(cfg, verifier, retriever, planner=[NO_PLAN], generator=["linear"], formalizer=[lean("linarith")])
    r = orch.solve(PROBLEM)
    assert r["solved"] and r["verified_by_lean"] and r["llm_calls"] == 3
    assert "theorem o1" in r["final_lean_code"]


def test_subgoal_then_main_uses_verified_lemma(cfg, verifier, retriever):
    orch, _ = make(cfg, verifier, retriever, planner=[ONE_SUBGOAL], generator=["s1", "main"],
                   formalizer=[lean("linarith"), lean("rw [subgoal_1 x h₀]\nnorm_num")])
    r = orch.solve(PROBLEM)
    assert r["solved"], r
    assert r["n_subgoals"] == 1 and r["lean_calls"] == 2
    assert "theorem subgoal_1" in r["final_lean_code"]


def test_critic_retry_fixes_the_proof(cfg, verifier, retriever):
    orch, _ = make(cfg, verifier, retriever, planner=[NO_PLAN], generator=["try"],
                   formalizer=[lean("norm_num"), lean("linarith")], critic=[RETRY])
    r = orch.solve(PROBLEM)
    assert r["solved"] and r["attempts"] == 2 and r["max_attempt_index_used"] == 1


def test_llm_claiming_success_is_not_enough(cfg, verifier, retriever):
    # RNF-1: el "generador" dice que está bien, pero Lean rechaza -> no resuelto.
    orch, _ = make(cfg, verifier, retriever, planner=[NO_PLAN], generator=["This is certainly correct."],
                   formalizer=[lean("norm_num")],
                   critic=['{"action": "abandon", "error_category": "other", "advice": "give up"}'])
    r = orch.solve(PROBLEM)
    assert not r["solved"] and not r["verified_by_lean"] and r["final_lean_code"] is None


def test_no_critic_configuration_fails_after_one_attempt(cfg, verifier, retriever):
    orch, _ = make(cfg, verifier, retriever, "no_critic", planner=[NO_PLAN], generator=["x"],
                   formalizer=[lean("norm_num")])
    r = orch.solve(PROBLEM)
    assert not r["solved"] and r["failure_reason"] == "rejected_without_critic" and r["attempts"] == 1


def test_budget_is_enforced(cfg, verifier, retriever):
    orch, llm = make(cfg, verifier, retriever, planner=[NO_PLAN], generator=["x"],
                     formalizer=[lean("norm_num")], critic=[RETRY])
    orch.opt.llm_call_budget = 5
    orch.critic.k_max = 99
    r = orch.solve(PROBLEM)
    assert not r["solved"] and r["failure_reason"] == "llm_call_budget_exhausted"
    assert r["llm_calls"] <= 5


def test_bad_subgoal_triggers_replan(cfg, verifier, retriever):
    bad = '{"subgoals": [{"informal": "?", "lean_decl": "theorem s (x : ℚ) : x = y"}]}'
    orch, _ = make(cfg, verifier, retriever, planner=[bad, NO_PLAN], generator=["x"],
                   formalizer=[lean("linarith")])
    r = orch.solve(PROBLEM)
    assert r["solved"] and r["replans"] == 1
    assert "planning_error" in r["error_categories"]


def test_no_rag_configuration_does_not_retrieve(cfg, verifier):
    orch, _ = make(cfg, verifier, None, "no_rag", planner=[NO_PLAN], generator=["x"], formalizer=[lean("linarith")])
    r = orch.solve(PROBLEM)
    assert r["solved"] and r["retrieval_calls"] == 0
