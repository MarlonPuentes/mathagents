"""Agente Verificador: ejecuta el kernel de Lean 4 (RF-5, RNF-1).

No usa IA. Arma un archivo .lean con:
    imports + opens + lemas ya verificados + <enunciado oficial> := by <tácticas>
    #print axioms <nombre>
y lo compila con `lake env lean`. Solo devuelve "accepted" si:
  1. Lean termina sin errores,
  2. no hay `sorry` (ni advertencia "declaration uses 'sorry'"),
  3. las tácticas no contienen trucos prohibidos (admit, axiom, #exit...),
  4. el teorema solo depende de los axiomas estándar de Lean/Mathlib.
El enunciado lo pone SIEMPRE el Verificador: el LLM solo aporta tácticas,
así no puede "resolver" un teorema cambiándolo por otro más fácil.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from core.schemas import validate
from core.text_utils import decl_name

FORBIDDEN_PATTERNS = {
    r"\bsorry\b": "uso de 'sorry'",
    r"\badmit\b": "uso de 'admit'",
    r"(^|\s)axiom\s": "declaración de axioma nuevo",
    r"#exit": "uso de '#exit'",
    r"\bunsafe\b": "código 'unsafe'",
    r"implemented_by": "atributo 'implemented_by'",
    r"debug\.skipKernelTC": "desactivar el chequeo del kernel",
    r"\bnative_decide\b": "'native_decide' (añade un axioma extra)",
}

_POSITION = re.compile(r"^(?P<file>.*?):(?P<line>\d+):(?P<col>\d+): (?P<kind>error|warning|info)(?:\(\S+\))?: ?(?P<msg>.*)$")


_AXIOM_LINE = re.compile(r"^'.+' (depends on axioms:|does not depend on any axioms)")


class LeanNotFoundError(Exception):
    """No se encontró `lake` (Lean no está instalado o no está en el PATH)."""


def find_lake() -> str:
    exe = shutil.which("lake")
    if exe:
        return exe
    candidate = Path.home() / ".elan" / "bin" / ("lake.exe" if os.name == "nt" else "lake")
    if candidate.exists():
        return str(candidate)
    raise LeanNotFoundError("No se encontró 'lake'. Instala Lean con elan (ver docs/instalacion.md).")


def _run_with_timeout(cmd: list[str], cwd: Path, timeout_s: int) -> tuple[int | None, str, bool]:
    """Ejecuta un comando; si se pasa del tiempo, mata el proceso y sus hijos."""
    kwargs: dict = dict(cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    try:
        out, _ = proc.communicate(timeout=timeout_s)
        return proc.returncode, out.decode("utf-8", errors="replace"), False
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        return None, out.decode("utf-8", errors="replace"), True


def parse_lean_messages(output: str) -> list[dict]:
    """Convierte la salida de Lean en una lista de mensajes {kind, line, col, msg}."""
    messages: list[dict] = []
    for raw in output.splitlines():
        m = _POSITION.match(raw)
        if m:
            messages.append({"kind": m["kind"], "line": int(m["line"]), "col": int(m["col"]),
                             "msg": m["msg"].strip()})
        elif _AXIOM_LINE.match(raw):
            # Lean imprime la salida de `#print axioms` sin prefijo de posición
            messages.append({"kind": "info", "line": -1, "col": -1, "msg": raw.strip()})
        elif messages:
            messages[-1]["msg"] += "\n" + raw  # continuación de un mensaje multilínea
    return messages


def _parse_axioms(messages: list[dict], name: str) -> list[str] | None:
    for msg in messages:
        text = msg["msg"]
        if f"'{name}'" not in text:
            continue
        if "does not depend on any axioms" in text:
            return []
        m = re.search(r"depends on axioms:\s*\[(.*?)\]", text, re.DOTALL)
        if m:
            return [a.strip() for a in m.group(1).split(",") if a.strip()]
    return None


class LeanVerifier:
    def __init__(self, project_dir: str | Path, imports: list[str], opens: list[str] | None = None,
                 timeout_s: int = 300, allowed_axioms: list[str] | None = None,
                 lake_cmd: str | None = None, keep_files: bool = False):
        self.project_dir = Path(project_dir).resolve()
        if not (self.project_dir / "lakefile.toml").exists() and not (self.project_dir / "lakefile.lean").exists():
            raise FileNotFoundError(f"No hay un proyecto Lean en {self.project_dir}")
        self.imports = imports
        self.opens = opens or []
        self.timeout_s = timeout_s
        self.allowed_axioms = set(allowed_axioms or ["propext", "Classical.choice", "Quot.sound"])
        self.lake = lake_cmd or find_lake()
        self.keep_files = keep_files
        self.work_dir = self.project_dir / ".verify_tmp"
        self.work_dir.mkdir(exist_ok=True)

    @classmethod
    def from_config(cls, cfg: dict, **kw) -> "LeanVerifier":
        from core.config import resolve_path
        lc = cfg["lean"]
        return cls(resolve_path(lc["project_dir"]), lc["imports"], lc.get("opens"),
                   lc.get("timeout_s", 300), lc.get("allowed_axioms"), **kw)

    # ------------------------------------------------------------------ armado del archivo
    def build_file(self, lean_decl: str, tactics: str, context_lemmas: list[str] | None = None) -> str:
        # autoImplicit false: sin esto Lean acepta identificadores desconocidos como variables
        # nuevas (ej. "x = foo" compila), lo que permitiría enunciados mal formalizados.
        header = "\n".join(f"import {m}" for m in self.imports)
        opens = f"open {' '.join(self.opens)}\n" if self.opens else ""
        context = "\n\n".join(context_lemmas or [])
        body = "\n".join("  " + ln if ln.strip() else "" for ln in tactics.splitlines())
        name = decl_name(lean_decl)
        return (f"{header}\n\nset_option maxHeartbeats 400000\nset_option autoImplicit false\n\n{opens}\n{context}\n\n"
                f"{lean_decl.rstrip()} := by\n{body}\n\n#print axioms {name}\n")

    @staticmethod
    def forbidden_constructs(tactics: str) -> list[str]:
        return [desc for pat, desc in FORBIDDEN_PATTERNS.items() if re.search(pat, tactics, re.MULTILINE)]

    # ------------------------------------------------------------------ ejecución
    def run_lean_file(self, code: str) -> tuple[int | None, str, bool, float]:
        path = self.work_dir / f"check_{uuid.uuid4().hex[:10]}.lean"
        path.write_text(code, encoding="utf-8")
        start = time.perf_counter()
        try:
            rc, out, timed_out = _run_with_timeout([self.lake, "env", "lean", str(path)],
                                                   self.project_dir, self.timeout_s)
        finally:
            if not self.keep_files:
                path.unlink(missing_ok=True)
        return rc, out, timed_out, time.perf_counter() - start

    def verify(self, lean_decl: str, tactics: str, context_lemmas: list[str] | None = None) -> dict:
        """Devuelve {verdict, errors, lean_code, duration_s, axioms, category_hint}."""
        name = decl_name(lean_decl)
        code = self.build_file(lean_decl, tactics or "", context_lemmas)
        if not name:
            return self._result("rejected", ["Declaración Lean sin nombre de teorema"], code, 0.0,
                                hint="planning_error")
        if not tactics or not tactics.strip():
            return self._result("rejected", ["No hay tácticas que verificar"], code, 0.0,
                                hint="formalization_failure")
        banned = self.forbidden_constructs(tactics)
        if banned:
            return self._result("rejected", [f"Construcción prohibida: {b}" for b in banned], code, 0.0,
                                hint="other")

        rc, out, timed_out, dur = self.run_lean_file(code)
        if timed_out:
            return self._result("rejected", [f"Tiempo límite de Lean ({self.timeout_s} s) excedido"],
                                code, dur, hint="timeout")
        messages = parse_lean_messages(out)
        errors = [f"línea {m['line']}:{m['col']}: {m['msg']}" for m in messages if m["kind"] == "error"]
        if any("declaration uses 'sorry'" in m["msg"] for m in messages):
            errors.append("La prueba usa 'sorry'")
        axioms = _parse_axioms(messages, name)
        if not errors and rc != 0:
            errors.append(f"Lean terminó con código {rc}: {out[-500:]}")
        if not errors:
            if axioms is None:
                errors.append("No se pudo leer la salida de '#print axioms'")
            else:
                extra = sorted(set(axioms) - self.allowed_axioms)
                if extra:
                    errors.append(f"Usa axiomas no permitidos: {extra}")
        verdict = "accepted" if not errors else "rejected"
        return self._result(verdict, errors, code, dur, axioms=axioms or [],
                            hint=self._hint(errors, lean_decl, code))

    def check_statement(self, lean_decl: str) -> dict:
        """Para curar el dataset: ¿el enunciado compila (con `sorry`) en esta versión de Mathlib?"""
        code = self.build_file(lean_decl, "sorry", None)
        rc, out, timed_out, dur = self.run_lean_file(code)
        messages = parse_lean_messages(out)
        errors = [f"línea {m['line']}:{m['col']}: {m['msg']}" for m in messages if m["kind"] == "error"]
        if timed_out:
            errors.append("timeout")
        return {"compiles": not errors, "errors": errors, "duration_s": round(dur, 3)}

    # ------------------------------------------------------------------ utilidades
    @staticmethod
    def _hint(errors: list[str], lean_decl: str, code: str) -> str | None:
        """Pista para el Crítico: ¿el error está en el ENUNCIADO del subobjetivo o en la prueba?

        Lean reporta "unsolved goals" en la posición de `by`, que está en la última línea
        del enunciado; por eso un error en esa línea, a partir del final del enunciado,
        se considera error de la PRUEBA y no del enunciado.
        """
        if not errors or not lean_decl.strip():
            return None
        decl = lean_decl.rstrip()
        first_line = code[:code.find(decl)].count("\n") + 1
        decl_lines = decl.splitlines()
        last_line = first_line + len(decl_lines) - 1
        last_len = len(decl_lines[-1])
        for e in errors:
            m = re.match(r"línea (\d+)(?::(\d+))?:", e)
            if not m:
                continue
            line = int(m.group(1))
            col = int(m.group(2)) if m.group(2) else 0
            if first_line <= line < last_line or (line == last_line and col < last_len):
                return "planning_error"
        return None

    @staticmethod
    def _result(verdict, errors, code, dur, axioms=None, hint=None) -> dict:
        res = {"verdict": verdict, "errors": errors, "lean_code": code,
               "duration_s": round(dur, 3), "axioms": axioms or [], "category_hint": hint}
        validate("verifier_output", res)
        return res


if __name__ == "__main__":  # prueba manual rápida: python -m agents.verifier
    from core.config import load_config
    v = LeanVerifier.from_config(load_config())
    r = v.verify("theorem prueba_manual : (2 : ℕ) + 2 = 4", "norm_num")
    print(r["verdict"], r["errors"])
    sys.exit(0 if r["verdict"] == "accepted" else 1)
