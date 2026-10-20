# Guía para reproducir cada ablación (sección 8.2 del PDF)

Antes de empezar: dataset curado (`data/problems_test.jsonl`), índice construido, LLM configurado
con `temperature: 0.0`, y `retrieval.model_revision` fijado. No cambies `config.yaml` entre corridas.

| Configuración | Comando |
| --- | --- |
| Línea base A (LLM único → Lean directo) | `python -m experiments.run_experiment --configuration baseline_a --split test --attempts 4` |
| Línea base B (LLM único, CoT, sin verificación) | `python -m experiments.run_experiment --configuration baseline_b --split test --check-baseline-b-with-lean` |
| Sistema sin RAG | `python -m experiments.run_experiment --configuration no_rag --split test` |
| Sistema sin Crítico (k_max = 1) | `python -m experiments.run_experiment --configuration no_critic --split test` |
| Sistema completo | `python -m experiments.run_experiment --configuration full --split test` |

Análisis conjunto:

```bash
python -m experiments.analyze results/baseline_a_test_*.jsonl results/baseline_b_test_*.jsonl \
    results/no_rag_test_*.jsonl results/no_critic_test_*.jsonl results/full_test_*.jsonl \
    --out results/summary_test.json
```

Reglas:

1. Ajusta prompts SOLO con el split `dev`. El split `test` se corre una vez al final.
2. Si una corrida se interrumpe, continúa con `--resume results/<archivo>.jsonl`.
3. Guarda `logs/` y `results/` completos: son la evidencia del informe.
4. La línea base B nunca cuenta como "resuelta": su éxito es autoevaluación del LLM.
