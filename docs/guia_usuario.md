# Guía de usuario

## Probar un teorema propio

```bash
python -m demo.app
```

Abre el navegador en la dirección que muestra la terminal, escribe el enunciado en lenguaje natural y en
Lean (sin prueba, empezando por `theorem nombre ...`) y pulsa "Resolver".

- **VERIFICADO POR LEAN**: el kernel de Lean aceptó la prueba completa. Es una demostración correcta
  del enunciado Lean que escribiste (revisa que ese enunciado diga lo que querías: mal-formalización).
- **NO VERIFICADO**: cualquier texto que veas en la traza es solo lo que generó el modelo.

## Leer un log

Cada línea de `logs/<run_id>.jsonl` es un JSON. La primera es el manifiesto. Para ver solo los pasos
de un problema en Python:

```python
from core.run_logger import read_log
steps = [r for r in read_log("logs/ARCHIVO.jsonl") if r.get("problem_id") == "mathd_algebra_10"]
```
