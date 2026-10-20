---
license: mit
task_categories: [text-generation]
tags: [lean4, theorem-proving, minif2f]
---
# Ficha del dataset

## Contenido

| Archivo | Qué es |
| --- | --- |
| `raw/minif2f.jsonl` | miniF2F en Lean 4 (488 problemas: 244 valid + 244 test), copia del repositorio DeepSeek-Prover-V1.5 (MIT) |
| `problems_dev.jsonl` / `problems_test.jsonl` | Subconjunto curado (se genera con `curate_dataset.py --check-lean`) |
| `unclassified_for_manual_review.jsonl` | Problemas sin área automática (AMC/AIME/IMO), para etiquetar a mano |
| `reference_trivial.jsonl` | 5 teoremas triviales para pruebas de integración (escritos por el equipo) |
| `retrieval_reference.jsonl` | Pares consulta-lema para medir la calidad del Recuperador |

## Campos de cada problema

`id`, `informal_statement`, `formal_statement` (Lean 4, sin prueba), `area` (algebra / number_theory /
combinatorics), `difficulty` (1 = MATH, 2 = AMC o ejercicio de libro, 3 = AIME/IMO), `split` (dev/test),
`source`, `lean_check` (ok si compila con `sorry` en Mathlib v4.34.1).

## Curación

1. Área por el nombre del problema (`algebra`, `numbertheory`); lo demás se etiqueta a mano.
2. Dificultad por la fuente del problema.
3. Muestra estratificada con semilla 42; dev = split valid de miniF2F, test = split test (disjuntos).
4. Se descartan enunciados que no compilan en la versión fijada de Mathlib.

## Limitaciones conocidas

- Las reglas automáticas solo etiquetan álgebra y teoría de números; el nivel 3 y la combinatoria
  requieren revisión manual o problemas de PutnamBench.
- miniF2F se escribió con versiones antiguas de Mathlib; algunos enunciados pueden haber cambiado
  de significado o dejado de compilar.

## Licencias

miniF2F: MIT. Versión Lean 4: repositorio DeepSeek-Prover-V1.5 (MIT). PutnamBench: revisar su licencia antes de incluir problemas.
