"""Paso 5: líneas base A (Lean directo) y B (solo lenguaje natural)."""
from helpers import lean, scripted
from orchestrator.baselines import run_baseline_a, run_baseline_b

PROBLEM = {"id": "b1", "informal_statement": "If x + 3 = 5 then x = 2.",
           "formal_statement": "theorem b1 (x : ℚ) (h₀ : x + 3 = 5) : x = 2"}


def test_baseline_a_counts_only_lean_verdict(verifier):
    llm = scripted(baseline_a=[lean("norm_num"), lean("linarith")])
    r = run_baseline_a(PROBLEM, llm, verifier, attempts=2)
    assert r["attempt_results"] == [False, True]
    assert r["solved"] is False          # pass@1 usa solo el primer intento
    assert r["n_correct"] == 1 and r["llm_calls"] == 2


def test_baseline_b_is_never_marked_as_solved():
    llm = scripted(baseline_b=["x = 5 - 3 = 2.\nSELF-ASSESSMENT: CORRECT"])
    r = run_baseline_b(PROBLEM, llm)
    assert r["self_assessed_correct"] is True
    assert r["solved"] is False and r["verified_by_lean"] is False and r["status"] == "unverified"


def test_baseline_b_false_positive_detected(verifier):
    llm = scripted(baseline_b=["Trivially x = 7.\nSELF-ASSESSMENT: CORRECT"], formalizer=[lean("norm_num")])
    r = run_baseline_b(PROBLEM, llm, verifier, check_with_lean=True)
    assert r["lean_check_of_self_assessed"] == "rejected"
    assert r["false_positive_caught"] is True
