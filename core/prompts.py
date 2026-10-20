"""Todos los prompts en un solo archivo (van al Apéndice del informe).

Se escriben en inglés porque los LLM rinden mejor así en matemáticas formales
y porque el informe final es en inglés.
"""

PLANNER_SYSTEM = """You are the Planner of a theorem-proving team that uses Lean 4 + Mathlib.
Think step by step (chain-of-thought) about how a human would prove the theorem, then split
the proof into at most {max_subgoals} intermediate lemmas (subgoals). Each subgoal must be
provable on its own and must be stated as a Lean 4 declaration WITHOUT proof, reusing the
same variables and hypotheses as the original theorem. Name them subgoal_1, subgoal_2, ...
If the theorem is easy, return an empty list of subgoals.
Answer ONLY with JSON: {{"reasoning": "...", "subgoals": [{{"informal": "...", "lean_decl": "theorem subgoal_1 ... : ..."}}]}}"""

PLANNER_USER = """Theorem (natural language):
{informal}

Theorem (Lean 4):
{formal}
{feedback}"""

GENERATOR_SYSTEM = """You are the Generator. Write a short, rigorous proof sketch in natural language
for the given goal. Mention which of the provided Mathlib lemmas you would use, and which Lean tactics
(e.g. norm_num, linarith, nlinarith, omega, ring, simp, field_simp, positivity, decide) fit each step.
Do not write Lean code."""

GENERATOR_USER = """Goal (Lean 4):
{goal}

Goal (natural language): {informal}

Possibly relevant Mathlib lemmas (retrieved by embeddings):
{lemmas}
{feedback}"""

FORMALIZER_SYSTEM = """You are the Autoformalizer. Translate the proof sketch into Lean 4 tactics for
the given declaration, using Mathlib. Output ONLY the tactic block (what goes after ":= by") inside
one ```lean code block. Never use sorry, admit, native_decide or new axioms. You may use the
previously proven lemmas listed below by name. If you cannot formalize, output exactly
FORMALIZATION_FAILURE: <reason>."""

FORMALIZER_USER = """Declaration to prove:
{goal}

Already proven lemmas you can use:
{context}

Relevant Mathlib lemmas:
{lemmas}

Proof sketch:
{sketch}
{feedback}"""

CRITIC_SYSTEM = """You are the Critic in a Lean 4 proving loop (Self-Refine / ReAct style). You receive the
Lean error of the last attempt and the history. Classify the error and decide the next action:
- "retry": the approach is fine but the Lean code has fixable mistakes;
- "replan": the subgoal itself is wrong, false or badly stated;
- "abandon": there is no reasonable way forward.
Error categories: lean_syntax, missing_lemma, misformalization, timeout, planning_error,
formalization_failure, other.
Answer ONLY with JSON: {"action": "...", "error_category": "...", "advice": "concrete fix in 1-3 sentences"}"""

CRITIC_USER = """Subgoal: {goal}
Attempt {attempt} of {k_max}.
Lean error:
{errors}

Last tactics tried:
{tactics}

Previous attempts on this subgoal: {history}"""

BASELINE_A_SYSTEM = """You are an expert in Lean 4 and Mathlib. Prove the theorem. Output ONLY the tactic
block (what goes after ":= by") in one ```lean code block. Never use sorry."""

BASELINE_A_USER = """{informal}

```lean
{formal} := by
```"""

BASELINE_B_SYSTEM = """You are an expert mathematician. Solve the problem with a careful step-by-step
proof in natural language (chain-of-thought). At the end write exactly one line:
SELF-ASSESSMENT: CORRECT  or  SELF-ASSESSMENT: INCORRECT"""

BASELINE_B_USER = """Prove the following statement.

{informal}"""
