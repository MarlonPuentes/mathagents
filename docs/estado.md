# Estado del proyecto (27 sep 2026)

## Probado (y cómo)

Entorno de desarrollo: Linux, Python 3.11, Lean 4 v4.34.1, Mathlib v4.34.1. El servidor de caché de
Mathlib no era accesible desde ese entorno, así que se compilaron solo los módulos
`Mathlib.Tactic.Linarith`, `Mathlib.Tactic.Ring` y `Mathlib.Tactic.NormNum.Basic` (837 archivos) y las
pruebas se corrieron con `MATHAGENTS_LEAN_IMPORTS` apuntando a ellos.

| Qué | Resultado |
| --- | --- |
| `pytest tests` con Lean real | 69 pruebas pasan |
| `pytest tests` sin Lean | 51 pasan, 18 se saltan con mensaje claro |
| `experiments.smoke_test` (LLM simulado + Lean real) | 5/5 teoremas triviales verificados |
| Verificador: rechaza `sorry`, axiomas nuevos, cambio de enunciado, identificadores inventados | probado |
| `ExtractDecls.lean` sobre el subconjunto compilado | 14 146 teoremas extraídos con notación legible |
| `curate_dataset.py` (sin `--check-lean`) | selecciona 15 dev + 45 test; 175 problemas quedan para etiquetado manual |
| Índice con embedder `hashing` + `eval_retrieval` | recall@10 = 1/8 en el corpus parcial: el embedder de prueba no es semántico, se necesita el modelo real |
| Demo Gradio | la interfaz se construye; no se lanzó en navegador |

## NO probado todavía

- Proveedores de LLM reales (`openai_compatible`, `anthropic`, `claude_cli`): no había clave.
- `sentence-transformers` con `BAAI/bge-small-en-v1.5`: huggingface.co no era accesible desde el entorno.
- `import Mathlib` completo y todo el flujo en Windows.
- `curate_dataset.py --check-lean` con Mathlib completo.
- Hugging Face Space con Lean dentro (necesita Dockerfile).

## Pendiente (según el cronograma del PDF)

1. Instalar en Windows y correr `pytest` + `smoke_test` (semanas 3-4).
2. Elegir LLM, correr líneas base A/B en `dev` (semanas 3-4).
3. Construir el índice real y medir `eval_retrieval` (semana 9).
4. Curar dataset final con `--check-lean` y etiquetado manual (semana 10).
5. Experimentos, análisis, informe (semanas 11-13).
