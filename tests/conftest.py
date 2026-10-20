"""Configuración común de pytest.

- Agrega la raíz del repo al path de Python.
- Fixture `verifier`: Lean real. Si Lean no está instalado, las pruebas que lo
  necesitan se SALTAN (skip) con un mensaje claro, en vez de fallar en silencio.
  Para exigir Lean (p. ej. en integración continua): MATHAGENTS_REQUIRE_LEAN=1
- En una máquina sin Mathlib completo se pueden usar solo algunos módulos:
  MATHAGENTS_LEAN_IMPORTS="Mathlib.Tactic.Linarith,Mathlib.Tactic.Ring,Mathlib.Tactic.NormNum.Basic"
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import load_config  # noqa: E402


@pytest.fixture(scope="session")
def cfg():
    return load_config(overrides={"retrieval.embedder": "hashing"})


@pytest.fixture(scope="session")
def verifier(cfg):
    from agents.verifier import LeanNotFoundError, LeanVerifier
    try:
        v = LeanVerifier.from_config(cfg)
    except (LeanNotFoundError, FileNotFoundError) as exc:
        if os.environ.get("MATHAGENTS_REQUIRE_LEAN") == "1":
            pytest.fail(f"Lean es obligatorio y no está disponible: {exc}")
        pytest.skip(f"Lean no disponible: {exc}")
    probe = v.verify("theorem probe_ok : (1 : ℕ) + 1 = 2", "norm_num")
    if probe["verdict"] != "accepted":
        msg = f"Lean/Mathlib no responde bien: {probe['errors'][:1]}"
        if os.environ.get("MATHAGENTS_REQUIRE_LEAN") == "1":
            pytest.fail(msg)
        pytest.skip(msg)
    return v
