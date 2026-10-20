---
title: MathAgents Lean Prover
sdk: gradio
app_file: app.py
license: apache-2.0
---
# Demo (Hugging Face Space)

Para publicarla, copia al Space el repositorio completo y usa `demo/app.py` como aplicación.
Necesita un LLM configurado (clave como *secret* `LLM_API_KEY` del Space) y Lean + Mathlib dentro del
contenedor, lo que requiere un Dockerfile propio (pendiente: no se ha probado un Space con Lean).
