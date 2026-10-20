"""Protocolo estadístico de la sección 8.4 del PDF.

- Wilson: intervalo de confianza para una proporción (tasa de éxito) con n pequeño.
- McNemar exacto: compara dos configuraciones sobre LOS MISMOS problemas.
  Solo importan los problemas "discordantes": b = A resuelve y B no; c = al revés.
- Bootstrap: intervalo de confianza de una media remuestreando 1000 veces.
- Bonferroni: corrige p-valores cuando se hacen muchas comparaciones.
- pass@k: estimador insesgado (Chen et al., 2021).
"""
from __future__ import annotations

from math import comb

import numpy as np
from scipy import stats as sps


def wilson_interval(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    if not 0 <= successes <= n:
        raise ValueError("successes debe estar entre 0 y n")
    z = sps.norm.ppf(1 - alpha / 2)
    p = successes / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def mcnemar_exact(results_a: list[bool], results_b: list[bool]) -> dict:
    if len(results_a) != len(results_b):
        raise ValueError("Las listas deben corresponder a los mismos problemas, en el mismo orden")
    b = sum(1 for x, y in zip(results_a, results_b) if x and not y)
    c = sum(1 for x, y in zip(results_a, results_b) if y and not x)
    n = b + c
    p = 1.0 if n == 0 else min(1.0, 2 * sps.binom.cdf(min(b, c), n, 0.5))
    return {"b_only_a": b, "c_only_b": c, "p_value": float(p)}


def bootstrap_mean_ci(values: list[float], n_resamples: int = 1000, alpha: float = 0.05,
                      seed: int = 42) -> tuple[float, float, float]:
    """Devuelve (media, límite inferior, límite superior)."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return (float("nan"), float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(arr, size=(n_resamples, arr.size), replace=True).mean(axis=1)
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(arr.mean()), float(lo), float(hi))


def median_iqr(values: list[float]) -> tuple[float, float, float]:
    """Devuelve (mediana, percentil 25, percentil 75)."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return (float("nan"),) * 3
    q1, med, q3 = np.percentile(arr, [25, 50, 75])
    return (float(med), float(q1), float(q3))


def bonferroni(p_values: list[float], n_comparisons: int | None = None) -> list[float]:
    m = n_comparisons or len(p_values)
    return [min(1.0, p * m) for p in p_values]


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probabilidad de que al menos uno de k intentos (de n hechos, c correctos) sea correcto."""
    if k > n:
        raise ValueError("k no puede ser mayor que n")
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)
