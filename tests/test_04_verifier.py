"""Paso 4: Verificador con Lean REAL (RF-5, RNF-1). Se salta si Lean no está instalado."""
from agents.verifier import LeanVerifier, parse_lean_messages


def test_parse_messages_offline():
    out = "f.lean:3:2: error: unsolved goals\nx : ℕ\n'foo' depends on axioms: [propext]"
    msgs = parse_lean_messages(out)
    assert msgs[0]["kind"] == "error" and "x : ℕ" in msgs[0]["msg"]
    assert msgs[1]["kind"] == "info"


def test_correct_proof_is_accepted(verifier):
    r = verifier.verify("theorem v_ok (x : ℚ) (h₀ : x + 3 = 5) : x = 2", "linarith")
    assert r["verdict"] == "accepted" and r["errors"] == []
    assert set(r["axioms"]) <= {"propext", "Classical.choice", "Quot.sound"}


def test_wrong_proof_is_rejected_with_trace(verifier):
    r = verifier.verify("theorem v_bad (x : ℚ) (h₀ : 2 * x = 4) : x = 3", "linarith")
    assert r["verdict"] == "rejected"
    assert any("linarith failed" in e for e in r["errors"])


def test_sorry_is_never_accepted(verifier):
    r = verifier.verify("theorem v_sorry : (1 : ℕ) = 1", "sorry")
    assert r["verdict"] == "rejected"


def test_new_axioms_are_rejected(verifier):
    r = verifier.verify("theorem v_ax : (1 : ℕ) = 2", "exact absurd rfl (by decide)\naxiom trampa : False")
    assert r["verdict"] == "rejected"


def test_llm_cannot_change_the_statement(verifier):
    # Aunque el LLM devuelva otro teorema, el Verificador usa el enunciado oficial.
    from core.text_utils import extract_tactics
    tactics = extract_tactics("```lean\ntheorem v_easy : True := by\n  trivial\n```")
    r = verifier.verify("theorem v_real (x : ℚ) (h : x = 1) : x = 2", tactics)
    assert r["verdict"] == "rejected"


def test_unknown_identifier_in_statement_is_planning_error(verifier):
    # autoImplicit false: 'y' no se convierte en variable nueva
    r = verifier.verify("theorem v_decl (x : ℚ) (h : x < 1) : x < y", "linarith")
    assert r["verdict"] == "rejected" and r["category_hint"] == "planning_error"


def test_context_lemmas_can_be_used(verifier):
    ctx = ["theorem subgoal_1 (x : ℚ) (h₀ : x + 3 = 5) : x = 2 := by\n  linarith"]
    r = verifier.verify("theorem v_main (x : ℚ) (h₀ : x + 3 = 5) : 2 * x = 4",
                        "rw [subgoal_1 x h₀]\nnorm_num", ctx)
    assert r["verdict"] == "accepted", r["errors"]
