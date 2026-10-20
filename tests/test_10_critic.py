"""Paso 10: Crítico/Refinador (RF-6)."""
from agents.base import StepContext
from agents.critic import Critic, classify_error
from helpers import scripted

SG = {"id": "sg1", "lean_decl": "theorem subgoal_1 : True", "is_main": False}
MAIN = {"id": "main", "lean_decl": "theorem t : True", "is_main": True}


def test_error_taxonomy():
    assert classify_error(["línea 3:1: Unknown identifier `foo_bar`"]) == "missing_lemma"
    assert classify_error(["línea 3:1: unexpected token ')'; expected term"]) == "lean_syntax"
    assert classify_error(["Tiempo límite de Lean (300 s) excedido"]) == "timeout"
    assert classify_error(["línea 5:2: linarith failed to find a contradiction"]) == "misformalization"
    assert classify_error(["cualquier cosa"], hint="planning_error") == "planning_error"


def test_retry_uses_llm_advice():
    llm = scripted(critic=['{"action": "retry", "error_category": "lean_syntax", "advice": "close the parenthesis"}'])
    out = Critic(llm, k_max=3).critique(SG, ["unexpected token"], "exact (h", 1, 0, [], StepContext())
    assert out == {"action": "retry", "error_category": "lean_syntax", "advice": "close the parenthesis"}


def test_k_max_forces_replan_then_abandon_without_llm():
    llm = scripted(critic=["no debería llamarse"])
    c = Critic(llm, k_max=2, max_replans=1)
    assert c.critique(SG, ["x"], "t", 2, 0, [], StepContext())["action"] == "replan"
    assert c.critique(SG, ["x"], "t", 2, 1, [], StepContext())["action"] == "abandon"
    assert llm.calls == 0


def test_bad_official_statement_is_abandoned_not_replanned():
    out = Critic(scripted(critic=["x"]), k_max=3).critique(MAIN, ["e"], "t", 1, 0, [], StepContext(), hint="planning_error")
    assert out["action"] == "abandon"


def test_unparseable_llm_answer_falls_back_to_rules():
    out = Critic(scripted(critic=["??"]), k_max=3).critique(SG, ["unexpected token"], "t", 1, 0, [], StepContext())
    assert out["action"] == "retry" and out["error_category"] == "lean_syntax"
