"""Paso 7: Generador (RF-3) y self-consistency."""
from agents.base import StepContext
from agents.generator import Generator, pick_consensus
from helpers import scripted

SUBGOAL = {"id": "sg1", "informal": "x = 2", "lean_decl": "theorem subgoal_1 (x : ℚ) (h₀ : x + 3 = 5) : x = 2"}


def test_generator_returns_sketch_and_uses_lemmas_in_prompt():
    llm = scripted(generator=["Subtract 3 from both sides; linarith."])
    out = Generator(llm).generate(SUBGOAL, [{"name": "add_comm", "statement": "a+b=b+a", "score": 0.9}], StepContext())
    assert out["sketch"].startswith("Subtract")
    assert "add_comm" in llm.prompts[0][1]


def test_self_consistency_picks_majority_like_sketch():
    cands = ["use linarith on h0", "use linarith with h0", "draw a triangle"]
    assert pick_consensus(cands) in cands[:2]


def test_n_samples_makes_n_calls():
    llm = scripted(generator=["a", "b", "a"])
    Generator(llm, n_samples=3).generate(SUBGOAL, [], StepContext())
    assert llm.calls == 3
