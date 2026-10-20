"""Demo Gradio (Hugging Face Space): escribe un teorema y mira a los agentes trabajar.

    python -m demo.app          # abre http://127.0.0.1:7860

Muestra dos cosas SEPARADAS a propósito:
  - VERIFICADO POR LEAN: solo si el kernel de Lean aceptó la prueba completa.
  - Trazas de los agentes: lo que generó el LLM (NO es una prueba hasta que Lean lo acepte).
Requiere un LLM real configurado (config.yaml) y Lean + Mathlib instalados.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from core.config import load_config
from core.run_logger import RunLogger, read_log

CONFIGS = ["full", "no_rag", "no_critic"]


def solve_theorem(informal: str, formal: str, configuration: str):
    from agents.verifier import LeanVerifier
    from core.llm_client import create_llm
    from orchestrator.pipeline import build_orchestrator

    if not formal.strip().startswith(("theorem", "lemma")):
        return "ERROR: el enunciado Lean debe empezar con 'theorem nombre ...'", "", ""
    try:
        cfg = load_config()
        log_path = Path(tempfile.mkdtemp()) / "demo.jsonl"
        logger = RunLogger(log_path)
        orch = build_orchestrator(configuration, cfg, create_llm(cfg), LeanVerifier.from_config(cfg), logger)
        result = orch.solve({"id": "demo", "informal_statement": informal or formal, "formal_statement": formal},
                            configuration)
    except Exception as exc:  # la demo muestra el error en pantalla en vez de caerse
        return f"ERROR: {type(exc).__name__}: {exc}", "", ""
    if result["solved"] and result["verified_by_lean"]:
        verdict = f"✅ VERIFICADO POR LEAN ({result['llm_calls']} llamadas LLM, {result['wall_time_s']} s)"
    else:
        verdict = f"❌ NO VERIFICADO — {result['failure_reason']} ({result['llm_calls']} llamadas LLM)"
    steps = [r for r in read_log(log_path) if r.get("event") == "agent_step"]
    trace = "\n".join(f"[{s['agent']}] subobjetivo={s['subgoal_id']} intento={s['attempt']} -> {s['decision']}"
                      for s in steps)
    return verdict, result.get("final_lean_code") or "(sin prueba verificada)", trace


def build_ui():
    import gradio as gr
    with gr.Blocks(title="Multi-agent theorem prover (Lean 4)") as ui:
        gr.Markdown("## Sistema multiagente con verificación formal en Lean 4\n"
                    "Una prueba solo cuenta cuando **Lean la acepta**. Todo lo demás es texto generado por el modelo.")
        informal = gr.Textbox(label="Enunciado en lenguaje natural", value="If x + 3 = 5 then x = 2.")
        formal = gr.Textbox(label="Enunciado en Lean 4 (sin prueba)",
                            value="theorem demo (x : ℝ) (h₀ : x + 3 = 5) : x = 2", lines=3)
        conf = gr.Dropdown(CONFIGS, value="full", label="Configuración")
        btn = gr.Button("Resolver")
        verdict = gr.Textbox(label="Veredicto")
        code = gr.Code(label="Prueba aceptada por Lean")
        trace = gr.Textbox(label="Traza de agentes (JSON Lines resumido)", lines=12)
        btn.click(solve_theorem, [informal, formal, conf], [verdict, code, trace])
    return ui


if __name__ == "__main__":
    build_ui().launch()
