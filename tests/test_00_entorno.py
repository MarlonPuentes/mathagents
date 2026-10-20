"""Paso 0: ¿el entorno tiene lo necesario?"""
import importlib
import sys

import pytest


def test_python_version():
    assert sys.version_info >= (3, 10), "Se necesita Python 3.10 o superior"


@pytest.mark.parametrize("module", ["langgraph", "jsonschema", "numpy", "scipy", "yaml"])
def test_required_libraries(module):
    importlib.import_module(module)


def test_lean_answers(verifier):
    """Si esta prueba se salta (SKIPPED), Lean no está instalado o Mathlib no compiló."""
    r = verifier.verify("theorem env_check : (2 : ℕ) + 2 = 4", "norm_num")
    assert r["verdict"] == "accepted", r["errors"]
