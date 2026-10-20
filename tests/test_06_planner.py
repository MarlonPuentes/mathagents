"""Paso 6: Planificador (RF-1)."""
from agents.base import StepContext
from agents.planner import Planner
from helpers import scripted

PROBLEM = {"id": "p", "informal_statement": "If x + 3 = 5 then 2x = 4.",
           "formal_statement": "theorem p_main (x : ℚ) (h₀ : x + 3 = 5) : 2 * x = 4 := by sorry"}


def test_subgoals_are_renamed_and_main_is_last():
    llm = scripted(planner=['{"subgoals": [{"informal": "x = 2", "lean_decl": "lemma foo (x : ℚ) (h₀ : x + 3 = 5) : x = 2 := by sorry"}]}'])
    out = Planner(llm).plan(PROBLEM, StepContext("p"))
    sgs = out["subgoals"]
    assert sgs[0]["lean_decl"] == "theorem subgoal_1 (x : ℚ) (h₀ : x + 3 = 5) : x = 2"
    assert sgs[-1]["is_main"] and sgs[-1]["lean_decl"] == "theorem p_main (x : ℚ) (h₀ : x + 3 = 5) : 2 * x = 4"


def test_garbage_answer_falls_back_to_single_goal():
    out = Planner(scripted(planner=["no sé"])).plan(PROBLEM, StepContext("p"))
    assert len(out["subgoals"]) == 1 and out["subgoals"][0]["is_main"]


def test_max_subgoals_is_respected():
    many = ",".join(f'{{"informal": "s", "lean_decl": "theorem s{i} : True"}}' for i in range(10))
    out = Planner(scripted(planner=[f'{{"subgoals": [{many}]}}']), max_subgoals=2).plan(PROBLEM, StepContext("p"))
    assert len(out["subgoals"]) == 3
