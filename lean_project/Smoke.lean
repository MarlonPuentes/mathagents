-- Prueba de humo del paso 0: si este archivo compila, Lean + Mathlib están bien instalados.
-- Ejecutar desde lean_project/:  lake env lean Smoke.lean
import Mathlib

theorem smoke_test (x : ℝ) (h₀ : x + 3 = 5) : x = 2 := by
  linarith

#print axioms smoke_test
