"""Registro estructurado en JSON Lines (RF-7 y RNF-5).

Cada línea del archivo es un evento: quién (agente), sobre qué (problema,
subobjetivo, intento), cuánto costó (tokens, latencia) y qué decidió.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _write(self, record: dict[str, Any]) -> None:
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock, open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def log_manifest(self, manifest: dict[str, Any]) -> None:
        self._write({"event": "manifest", **manifest})

    def log_agent_step(self, *, problem_id: str, agent: str, attempt: int,
                       decision: str, subgoal_id: str | None = None,
                       input_tokens: int = 0, output_tokens: int = 0,
                       latency_s: float = 0.0, llm_calls: int = 0,
                       details: dict | None = None) -> None:
        """Una fila por agente e intento (RF-7)."""
        self._write({
            "event": "agent_step",
            "problem_id": problem_id,
            "agent": agent,
            "subgoal_id": subgoal_id,
            "attempt": attempt,
            "decision": decision,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_s": round(latency_s, 4),
            "llm_calls": llm_calls,
            "details": details or {},
        })

    def log_problem_result(self, result: dict[str, Any]) -> None:
        self._write({"event": "problem_result", **result})


def read_log(path: str | Path) -> list[dict]:
    """Lee un log JSONL; ignora líneas dañadas pero avisa cuántas hubo."""
    records, bad = [], 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    if bad:
        print(f"[read_log] Aviso: {bad} líneas no eran JSON válido en {path}")
    return records


class Timer:
    """Uso: with Timer() as t: ...; luego t.elapsed."""

    def __enter__(self):
        self._start = time.perf_counter()
        self.elapsed = 0.0
        return self

    def __exit__(self, *exc):
        self.elapsed = time.perf_counter() - self._start
        return False
