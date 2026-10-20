# Referencia de interfaces por agente

Los esquemas completos están en `core/schemas.py` y se validan en cada llamada.

| Agente | Método | Entrada | Salida (esquema) | LLM |
| --- | --- | --- | --- | --- |
| Planner | `plan(problem, ctx, feedback)` | `problem` | `planner_output`: `subgoals[]` con `id`, `informal`, `lean_decl`, `is_main` | sí (1 llamada) |
| Retriever | `retrieve(subgoal, ctx)` | subobjetivo | `retriever_output`: `lemmas[]` (`name`, `statement`, `module`, `score`), `query_embedding_dim` | no |
| Generator | `generate(subgoal, lemmas, ctx, feedback)` | subobjetivo + lemas | `generator_output`: `sketch`, `candidates[]` | sí (n_samples llamadas) |
| Autoformalizer | `formalize(subgoal, sketch, lemmas, context_lemmas, ctx, feedback)` | boceto | `autoformalizer_output`: `status` = `ok` + `tactics`, o `formalization_failure` + `reason` | sí (1) |
| LeanVerifier | `verify(lean_decl, tactics, context_lemmas)` | código | `verifier_output`: `verdict`, `errors[]`, `lean_code`, `duration_s`, `axioms[]` | no |
| Critic | `critique(subgoal, errors, tactics, attempt, replans_done, history, ctx, hint)` | error + historial | `critic_output`: `action` (retry/replan/abandon), `error_category`, `advice` | sí (0 o 1) |

Categorías de error (taxonomía de la sección 8.3): `lean_syntax`, `missing_lemma`, `misformalization`,
`timeout`, `planning_error`, `formalization_failure`, `other`.

Cada llamada deja una fila `agent_step` en el log con `problem_id`, `agent`, `subgoal_id`, `attempt`,
`decision`, `input_tokens`, `output_tokens`, `latency_s`, `llm_calls` (RF-7).
