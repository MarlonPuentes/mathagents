"""Paso 1: configuración, manifiesto de reproducibilidad (RNF-2) y log JSONL (RF-7, RNF-5)."""
import json

import pytest

from core.config import ConfigError, build_manifest, load_config
from core.run_logger import RunLogger, read_log


def test_overrides_are_applied():
    cfg = load_config(overrides={"orchestrator.k_max": 5})
    assert cfg["orchestrator"]["k_max"] == 5


def test_invalid_k_max_is_rejected():
    with pytest.raises(ConfigError):
        load_config(overrides={"orchestrator.k_max": 0})


def test_manifest_has_reproducibility_fields(cfg):
    m = build_manifest(cfg, "full")
    for key in ["seed", "llm_model", "llm_temperature", "embedding_model", "mathlib_rev", "lean_toolchain"]:
        assert key in m
    assert m["mathlib_rev"] == "v4.34.1"


def test_logger_writes_one_json_per_line(tmp_path):
    log = RunLogger(tmp_path / "run.jsonl")
    log.log_manifest({"seed": 1})
    log.log_agent_step(problem_id="p1", agent="planner", attempt=0, decision="planned",
                       input_tokens=10, output_tokens=5, latency_s=0.5, llm_calls=1)
    lines = (tmp_path / "run.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    step = json.loads(lines[1])
    assert step["agent"] == "planner" and step["input_tokens"] == 10 and step["decision"] == "planned"
    assert len(read_log(tmp_path / "run.jsonl")) == 2
