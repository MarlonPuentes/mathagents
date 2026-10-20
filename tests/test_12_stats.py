"""Paso 12: estadística (sección 8.4), comprobada contra valores conocidos a mano."""
import pytest

from experiments.stats import (bonferroni, bootstrap_mean_ci, mcnemar_exact, median_iqr,
                               pass_at_k, wilson_interval)


def test_wilson_known_value():
    lo, hi = wilson_interval(5, 10)          # valor de referencia: (0.2366, 0.7634)
    assert lo == pytest.approx(0.2366, abs=1e-4) and hi == pytest.approx(0.7634, abs=1e-4)


def test_mcnemar_exact_known_value():
    a = [True] * 1 + [False] * 6 + [True] * 3
    b = [False] * 1 + [True] * 6 + [True] * 3   # b=1, c=6 -> p = 2*(1+7)/128 = 0.125
    r = mcnemar_exact(a, b)
    assert (r["b_only_a"], r["c_only_b"]) == (1, 6) and r["p_value"] == pytest.approx(0.125)


def test_mcnemar_no_discordant_pairs():
    assert mcnemar_exact([True, False], [True, False])["p_value"] == 1.0


def test_bootstrap_is_reproducible_and_contains_mean():
    vals = [3, 5, 7, 9, 11]
    m1 = bootstrap_mean_ci(vals, seed=1)
    assert m1 == bootstrap_mean_ci(vals, seed=1)
    assert m1[1] <= m1[0] == 7 <= m1[2]


def test_median_iqr_and_bonferroni():
    assert median_iqr([1, 2, 3, 4, 5]) == (3.0, 2.0, 4.0)
    assert bonferroni([0.01, 0.2], n_comparisons=10) == [0.1, 1.0]


def test_pass_at_k():
    assert pass_at_k(4, 0, 2) == 0.0
    assert pass_at_k(4, 1, 1) == pytest.approx(0.25)
    assert pass_at_k(4, 1, 4) == 1.0
