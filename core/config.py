"""Carga de configuración, semilla global y manifiesto de reproducibilidad (RNF-2)."""
from __future__ import annotations

import copy
import os
import platform
import random
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """Error en el archivo de configuración."""


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict:
    """Lee config.yaml y aplica cambios opcionales (útil en pruebas y ablaciones).

    `overrides` usa claves con puntos: {"orchestrator.k_max": 1}.
    """
    path = Path(path) if path else REPO_ROOT / "config.yaml"
    if not path.exists():
        raise ConfigError(f"No existe el archivo de configuración: {path}")
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    cfg = copy.deepcopy(cfg)
    for dotted_key, value in (overrides or {}).items():
        node = cfg
        *parents, last = dotted_key.split(".")
        for key in parents:
            node = node.setdefault(key, {})
        node[last] = value
    # Atajo para pruebas: MATHAGENTS_LEAN_IMPORTS="Mathlib.Tactic.Linarith,Mathlib.Tactic.Ring"
    env_imports = os.environ.get("MATHAGENTS_LEAN_IMPORTS")
    if env_imports and "lean.imports" not in (overrides or {}):
        cfg["lean"]["imports"] = [m.strip() for m in env_imports.split(",") if m.strip()]
        cfg["lean"]["opens"] = []
    _validate(cfg)
    return cfg


def _validate(cfg: dict) -> None:
    required = ["seed", "llm", "lean", "retrieval", "agents", "orchestrator"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ConfigError(f"Faltan secciones en la configuración: {missing}")
    if cfg["orchestrator"]["k_max"] < 1:
        raise ConfigError("orchestrator.k_max debe ser >= 1")


def set_global_seed(seed: int) -> None:
    """Fija la semilla de random y numpy (y torch si está instalado)."""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch  # type: ignore
        torch.manual_seed(seed)
    except ImportError:
        pass


def resolve_path(relative: str | Path) -> Path:
    """Convierte una ruta relativa del config en ruta absoluta desde la raíz del repo."""
    p = Path(relative)
    return p if p.is_absolute() else REPO_ROOT / p


def _read_mathlib_rev(lean_dir: Path) -> str | None:
    lakefile = lean_dir / "lakefile.toml"
    if not lakefile.exists():
        return None
    match = re.search(r'rev\s*=\s*"([^"]+)"', lakefile.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def _read_toolchain(lean_dir: Path) -> str | None:
    f = lean_dir / "lean-toolchain"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None


def _pkg_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def build_manifest(cfg: dict, configuration_name: str = "") -> dict[str, Any]:
    """Todo lo necesario para repetir una corrida (RNF-2)."""
    lean_dir = resolve_path(cfg["lean"]["project_dir"])
    return {
        "configuration": configuration_name,
        "seed": cfg["seed"],
        "llm_provider": cfg["llm"]["provider"],
        "llm_model": cfg["llm"]["model"],
        "llm_temperature": cfg["llm"]["temperature"],
        "embedding_model": cfg["retrieval"]["model_name"],
        "embedding_model_revision": cfg["retrieval"].get("model_revision"),
        "embedder": cfg["retrieval"]["embedder"],
        "lean_toolchain": _read_toolchain(lean_dir),
        "mathlib_rev": _read_mathlib_rev(lean_dir),
        "k_max": cfg["orchestrator"]["k_max"],
        "llm_call_budget": cfg["orchestrator"]["llm_call_budget"],
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {p: _pkg_version(p) for p in
                     ["langgraph", "sentence-transformers", "faiss-cpu", "openai", "anthropic"]},
        "git_commit": _git_commit(),
    }
