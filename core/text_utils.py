"""Utilidades para sacar JSON o código Lean del texto que devuelve un LLM.

Los LLM suelen envolver su respuesta en bloques ```json o ```lean y añadir
texto alrededor; estas funciones extraen solo la parte útil.
"""
from __future__ import annotations

import json
import re

_FENCE = re.compile(r"```(?P<lang>[a-zA-Z0-9_+-]*)[ \t]*\n(?P<body>.*?)```", re.DOTALL)


def extract_code_blocks(text: str, lang: str | None = None) -> list[str]:
    blocks = []
    for m in _FENCE.finditer(text):
        if lang is None or m.group("lang").lower() == lang.lower():
            blocks.append(m.group("body").strip("\n"))
    return blocks


def extract_json(text: str) -> dict | list | None:
    """Devuelve el primer JSON válido encontrado, o None."""
    candidates = extract_code_blocks(text, "json") + extract_code_blocks(text, "")
    candidates.append(text)
    for cand in candidates:
        cand = cand.strip()
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
        # Busca el primer objeto { ... } balanceado dentro del texto
        start = cand.find("{")
        while start != -1:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(cand)):
                ch = cand[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                elif ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(cand[start:i + 1])
                        except json.JSONDecodeError:
                            break
            start = cand.find("{", start + 1)
    return None


_BY = re.compile(r":=\s*by\b")


def extract_tactics(text: str) -> str | None:
    """Obtiene SOLO las tácticas de la prueba.

    Si el LLM devuelve un teorema completo ("theorem x ... := by tac"), se
    descarta el encabezado: el enunciado siempre lo pone el Verificador
    (así el LLM no puede cambiar el teorema; ver RNF-1).
    """
    blocks = extract_code_blocks(text, "lean") or extract_code_blocks(text, "lean4") \
        or extract_code_blocks(text, "")
    body = blocks[0] if blocks else text
    match = _BY.search(body)
    if match:
        body = body[match.end():]
    elif re.match(r"^\s*(theorem|lemma)\b", body):
        return None  # teorema sin ":= by": prueba en modo término, no soportada
    lines = [ln.rstrip() for ln in body.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return None
    indent = min(len(ln) - len(ln.lstrip()) for ln in lines if ln.strip())
    return "\n".join(ln[indent:] for ln in lines)


def brackets_balanced(code: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{", "⟩": "⟨"}
    stack: list[str] = []
    for ch in code:
        if ch in "([{⟨":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack


def decl_name(lean_decl: str) -> str | None:
    """'theorem foo (x : ℕ) : x = x' -> 'foo'."""
    m = re.match(r"^\s*(?:theorem|lemma)\s+([^\s(:{\[]+)", lean_decl)
    return m.group(1) if m else None


def strip_proof(formal_statement: str) -> str:
    """Quita ':= by sorry' o ':= by' del final de un enunciado del dataset."""
    s = formal_statement.rstrip()
    s = re.sub(r":=\s*by\s*(sorry)?\s*$", "", s)
    s = re.sub(r":=\s*sorry\s*$", "", s)
    return s.rstrip()
