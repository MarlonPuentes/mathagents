"""Paso 3: contratos JSON Schema (RNF-4)."""
import pytest

from core.schemas import ContractError, validate


def test_valid_planner_output():
    validate("planner_output", {"subgoals": [{"id": "sg1", "informal": "x", "lean_decl": "theorem subgoal_1 : True"}]})


def test_planner_output_without_subgoals_fails():
    with pytest.raises(ContractError):
        validate("planner_output", {"subgoals": []})


def test_autoformalizer_ok_requires_tactics():
    with pytest.raises(ContractError):
        validate("autoformalizer_output", {"status": "ok"})
    validate("autoformalizer_output", {"status": "formalization_failure", "reason": "no idea"})


def test_retriever_contract_includes_embedding_dim():
    with pytest.raises(ContractError):
        validate("retriever_output", {"lemmas": []})


def test_critic_action_must_be_known():
    with pytest.raises(ContractError):
        validate("critic_output", {"action": "maybe", "error_category": "other", "advice": ""})
