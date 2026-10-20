"""Contratos de entrada/salida de cada agente como JSON Schema (RNF-4, sección 6.3 del PDF).

Un contrato es un "tipo" para datos JSON: dice qué campos son obligatorios y
de qué tipo. Si un agente devuelve algo que no cumple su contrato, `validate`
lanza ContractError y el problema se detecta en el agente que falló, no tres
pasos después.
"""
from __future__ import annotations

from jsonschema import Draft202012Validator

ERROR_CATEGORIES = ["lean_syntax", "missing_lemma", "misformalization", "timeout",
                    "planning_error", "formalization_failure", "other"]

_SUBGOAL = {
    "type": "object",
    "required": ["id", "informal", "lean_decl"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "informal": {"type": "string"},
        # Declaración Lean completa SIN prueba, ej: "theorem subgoal_1 (x : ℝ) (h : x = 2) : x + 1 = 3"
        "lean_decl": {"type": "string", "pattern": r"^\s*(theorem|lemma)\s+\S+"},
        "is_main": {"type": "boolean"},
    },
}

_LEMMA = {
    "type": "object",
    "required": ["name", "statement", "score"],
    "properties": {
        "name": {"type": "string"},
        "statement": {"type": "string"},
        "score": {"type": "number"},
        "module": {"type": ["string", "null"]},
    },
}

SCHEMAS: dict[str, dict] = {
    "problem": {
        "type": "object",
        "required": ["id", "informal_statement", "formal_statement"],
        "properties": {
            "id": {"type": "string"},
            "informal_statement": {"type": "string"},
            "formal_statement": {"type": "string", "pattern": r"^\s*(theorem|lemma)\s+\S+"},
            "area": {"type": "string"},
            "difficulty": {"type": "integer"},
            "split": {"type": "string"},
            "source": {"type": "string"},
        },
    },
    "planner_output": {
        "type": "object",
        "required": ["subgoals"],
        "properties": {"subgoals": {"type": "array", "minItems": 1, "items": _SUBGOAL}},
    },
    "retriever_output": {
        "type": "object",
        "required": ["lemmas", "query_embedding_dim"],
        "properties": {
            "lemmas": {"type": "array", "items": _LEMMA},
            "query_embedding_dim": {"type": "integer", "minimum": 1},
        },
    },
    "generator_output": {
        "type": "object",
        "required": ["sketch"],
        "properties": {"sketch": {"type": "string", "minLength": 1},
                       "candidates": {"type": "array", "items": {"type": "string"}}},
    },
    "autoformalizer_output": {
        "type": "object",
        "required": ["status"],
        "properties": {
            "status": {"enum": ["ok", "formalization_failure"]},
            "tactics": {"type": "string"},
            "reason": {"type": "string"},
        },
        "if": {"properties": {"status": {"const": "ok"}}},
        "then": {"required": ["tactics"], "properties": {"tactics": {"minLength": 1}}},
        "else": {"required": ["reason"]},
    },
    "verifier_output": {
        "type": "object",
        "required": ["verdict", "errors", "lean_code", "duration_s"],
        "properties": {
            "verdict": {"enum": ["accepted", "rejected"]},
            "errors": {"type": "array", "items": {"type": "string"}},
            "lean_code": {"type": "string"},
            "duration_s": {"type": "number"},
            "axioms": {"type": "array", "items": {"type": "string"}},
        },
    },
    "critic_output": {
        "type": "object",
        "required": ["action", "error_category", "advice"],
        "properties": {
            "action": {"enum": ["retry", "replan", "abandon"]},
            "error_category": {"enum": ERROR_CATEGORIES},
            "advice": {"type": "string"},
        },
    },
}


class ContractError(Exception):
    """Un agente produjo (o recibió) datos que no cumplen su contrato."""


def validate(schema_name: str, data: dict) -> dict:
    """Valida `data` contra el esquema; devuelve el mismo dato si es válido."""
    if schema_name not in SCHEMAS:
        raise KeyError(f"Esquema desconocido: {schema_name}")
    validator = Draft202012Validator(SCHEMAS[schema_name])
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        msgs = "; ".join(f"{'/'.join(map(str, e.path)) or '(raíz)'}: {e.message}" for e in errors[:5])
        raise ContractError(f"[{schema_name}] {msgs}")
    return data


# Verificación de que los propios esquemas están bien escritos (se ejecuta al importar).
for _name, _schema in SCHEMAS.items():
    Draft202012Validator.check_schema(_schema)
