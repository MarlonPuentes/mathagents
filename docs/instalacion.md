# Guía de instalación (Windows 10/11)

Tiempo estimado: depende de tu internet; la descarga de Mathlib es de varios GB.
Requisitos: ~8 GB de espacio libre, 8 GB de RAM.

## 1. Copiar el proyecto a una ruta corta y sin espacios

Lean y Git en Windows tienen problemas con rutas largas o con espacios (tu usuario es
`Marlon Puentes`, con espacio). Copia la carpeta `mathagents` a:

```
C:\proyectos\mathagents
```

y activa rutas largas en Git (una sola vez):

```powershell
git config --global core.longpaths true
```

## 2. Python 3.12

1. Descarga Python 3.12 de python.org. En el instalador marca **"Add python.exe to PATH"**.
2. Comprueba: `py -3.12 --version`

## 3. Lean 4 (elan)

En PowerShell:

```powershell
curl -O --location https://raw.githubusercontent.com/leanprover/elan/master/elan-init.ps1
powershell -ExecutionPolicy Bypass -f elan-init.ps1
del elan-init.ps1
```

Cierra y abre la terminal. Comprueba: `elan --version`.
La versión de Lean (`v4.34.1`) la elige sola el archivo `lean_project/lean-toolchain`.

## 4. Mathlib precompilada

```powershell
cd C:\proyectos\mathagents\lean_project
lake exe cache get
lake env lean Smoke.lean
```

`lake exe cache get` descarga Mathlib ya compilada (no la compiles tú: tarda horas).
**Prueba del paso:** `Smoke.lean` debe terminar sin errores y mostrar
`'smoke_test' depends on axioms: [propext, Classical.choice, Quot.sound]`.

## 5. Entorno de Python

```powershell
cd C:\proyectos\mathagents
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Prueba del paso:** `pytest -q tests` debe terminar sin fallos (F). Si ves pruebas
"skipped", Lean no se encontró: revisa el paso 3.

## 6. Prueba de integración

```powershell
python -m experiments.smoke_test
```

Debe verificar los 5 teoremas triviales. Esto prueba la tubería, no la IA.

## 7. Índice de embeddings de Mathlib

```powershell
cd lean_project
lake env lean --run scripts/ExtractDecls.lean Mathlib ../retrieval/mathlib_decls.jsonl Mathlib.Algebra Mathlib.NumberTheory Mathlib.Combinatorics Mathlib.Data.Nat Mathlib.Data.Int Mathlib.Data.Real Mathlib.Order
cd ..
python -m retrieval.build_index --decls retrieval/mathlib_decls.jsonl
python -m experiments.eval_retrieval
```

El primer uso descarga el modelo `BAAI/bge-small-en-v1.5` desde Hugging Face. En CPU, calcular
los embeddings puede tardar bastante; hazlo una sola vez y guarda la carpeta `retrieval/index/`.
Antes de los experimentos, fija `retrieval.model_revision` en `config.yaml` al commit exacto del modelo.

## 8. Configurar el LLM

Edita `config.yaml`:

```yaml
llm:
  provider: openai_compatible
  model: "NOMBRE_DEL_MODELO"
  base_url: "URL_DEL_PROVEEDOR"
  temperature: 0.0
```

y define la clave en la terminal (no la escribas en archivos que vayas a publicar):

```powershell
$env:LLM_API_KEY = "tu_clave"
```

Nota: la suscripción Claude Pro **no** incluye la API. `provider: claude_cli` usa tu suscripción
mediante Claude Code, pero es experimental y no permite fijar la temperatura (incumple RNF-2).

## Problemas comunes

| Síntoma | Causa probable | Solución |
| --- | --- | --- |
| `No se encontró 'lake'` | elan no está en el PATH | Cierra y abre la terminal; revisa `%USERPROFILE%\.elan\bin` |
| `lake exe cache get` falla | Red o ruta con espacios | Ruta corta (paso 1), reintentar |
| Error `unknown package 'Mathlib'` | Falta el paso 4 | Ejecuta `lake exe cache get` dentro de `lean_project` |
| Todas las pruebas de Lean "skipped" | Lean no responde | Ejecuta `python -m agents.verifier` y lee el error |
