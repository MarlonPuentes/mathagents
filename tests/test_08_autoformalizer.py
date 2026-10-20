"""Paso 8: Autoformalizador (RF-4)."""
from agents.autoformalizer import Autoformalizer
from agents.base import StepContext
from helpers import lean, scripted

SUBGOAL = {"id": "sg1", "informal": "", "lean_decl": "theorem subgoal_1 (x : ℚ) (h₀ : x + 3 = 5) : x = 2"}


def run(answer):
    return Autoformalizer(scripted(formalizer=[answer])).formalize(SUBGOAL, "sketch", [], [], StepContext())


def test_extracts_tactics_from_lean_block():
    assert run(lean("linarith")) == {"status": "ok", "tactics": "linarith"}


def test_full_theorem_is_reduced_to_tactics():
    out = run(lean("theorem otro : True := by\n  have h := 1\n  linarith"))
    assert out["tactics"] == "have h := 1\nlinarith"


def test_explicit_failure_is_reported():
    out = run("FORMALIZATION_FAILURE: needs complex numbers")
    assert out["status"] == "formalization_failure" and "complex" in out["reason"]


def test_unbalanced_code_is_a_failure():
    assert run(lean("exact (foo"))["status"] == "formalization_failure"
