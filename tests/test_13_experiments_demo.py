"""Paso 14 (parte de software): runner, análisis y demo. Los datos de aquí son DE PRUEBA, no resultados."""
import json

import pytest

from experiments import analyze, run_experiment


def test_runner_refuses_mock_llm(capsys):
    assert run_experiment.main(["--configuration", "full", "--split", "reference"]) == 2
    assert "mock" in capsys.readouterr().err


def test_reference_split_loads_and_validates():
    probs = run_experiment.load_problems("reference")
    assert len(probs) == 5


def test_analyze_counts_only_lean_verified(tmp_path):
    rows = [
        {"problem_id": "a", "configuration": "full", "solved": True, "verified_by_lean": True, "llm_calls": 4},
        {"problem_id": "b", "configuration": "full", "solved": False, "verified_by_lean": False, "llm_calls": 20},
        {"problem_id": "a", "configuration": "no_rag", "solved": False, "verified_by_lean": False},
        {"problem_id": "b", "configuration": "no_rag", "solved": True, "verified_by_lean": False},  # inconsistente: no cuenta
        {"problem_id": "a", "configuration": "baseline_b", "self_assessed_correct": True,
         "lean_check_of_self_assessed": "rejected", "false_positive_caught": True},
    ]
    f = tmp_path / "r.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    by = analyze.load_results([str(f)])
    full = analyze.summarize("full", by["full"])
    assert full["solved"] == 1 and full["llm_calls_per_solved"]["mean"] == 4
    assert analyze.summarize("no_rag", by["no_rag"])["solved"] == 0
    assert analyze.summarize("baseline_b", by["baseline_b"])["false_positives_caught"] == 1
    comp = analyze.paired_comparisons(by)
    assert comp[0]["n_common"] == 2


def test_demo_builds_and_rejects_bad_input():
    pytest.importorskip("gradio")
    from demo.app import build_ui, solve_theorem
    assert build_ui() is not None
    verdict, _, _ = solve_theorem("x", "no es un teorema", "full")
    assert verdict.startswith("ERROR")
