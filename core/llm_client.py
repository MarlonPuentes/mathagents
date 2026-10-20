"""Cliente único para hablar con cualquier LLM.

Todos los agentes llaman a `llm.complete(system, user)` y reciben un
`LLMResponse`. Así cambiar de proveedor es cambiar una línea en config.yaml.

Proveedores:
- MockLLM: respuestas guardadas de antemano (pruebas, sin internet, sin costo).
- OpenAICompatibleLLM: cualquier API con formato OpenAI (Gemini, Groq,
  OpenRouter, DeepSeek, Ollama...). Implementado, NO probado con clave real aquí.
- AnthropicLLM: API de Anthropic (se paga aparte de Claude Pro). NO probado aquí.
- ClaudeCLILLM: EXPERIMENTAL. Usa `claude -p` con tu suscripción; no permite
  fijar temperatura (rompe RNF-2). NO probado aquí.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable


class LLMError(Exception):
    """Error al llamar al LLM (red, clave inválida, respuesta vacía...)."""


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    model: str
    tokens_are_estimated: bool = False


def estimate_tokens(text: str) -> int:
    """Aproximación grosera (≈4 caracteres por token). Solo para el mock."""
    return max(1, len(text) // 4)


@dataclass
class BaseLLM:
    model: str = "unknown"
    temperature: float = 0.0
    max_tokens: int = 2048
    calls: int = field(default=0, init=False)
    total_input_tokens: int = field(default=0, init=False)
    total_output_tokens: int = field(default=0, init=False)

    def complete(self, system: str, user: str) -> LLMResponse:
        start = time.perf_counter()
        resp = self._complete(system, user)
        resp.latency_s = time.perf_counter() - start
        if not resp.text or not resp.text.strip():
            raise LLMError(f"El modelo {self.model} devolvió una respuesta vacía")
        self.calls += 1
        self.total_input_tokens += resp.input_tokens
        self.total_output_tokens += resp.output_tokens
        return resp

    def _complete(self, system: str, user: str) -> LLMResponse:  # pragma: no cover
        raise NotImplementedError


class MockLLM(BaseLLM):
    """LLM simulado.

    `responder` puede ser:
    - una lista de strings: se devuelven en orden;
    - una función (system, user) -> str: decide la respuesta según el prompt.
    """

    def __init__(self, responder: list[str] | Callable[[str, str], str], model: str = "mock-model"):
        super().__init__(model=model)
        self._queue = list(responder) if isinstance(responder, list) else None
        self._fn = responder if callable(responder) else None
        self.prompts: list[tuple[str, str]] = []  # para inspeccionar en pruebas

    def _complete(self, system: str, user: str) -> LLMResponse:
        self.prompts.append((system, user))
        if self._fn is not None:
            text = self._fn(system, user)
        elif self._queue:
            text = self._queue.pop(0)
        else:
            raise LLMError("MockLLM: no quedan respuestas simuladas")
        return LLMResponse(text=text, input_tokens=estimate_tokens(system + user),
                           output_tokens=estimate_tokens(text), latency_s=0.0,
                           model=self.model, tokens_are_estimated=True)


def _with_retries(fn: Callable[[], LLMResponse], max_retries: int) -> LLMResponse:
    """Reintenta con espera exponencial (1 s, 2 s, 4 s...) ante fallos transitorios."""
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except LLMError:
            raise
        except Exception as exc:  # errores de red / límite de uso del proveedor
            last_error = exc
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    raise LLMError(f"Falló tras {max_retries + 1} intentos: {last_error}")


class OpenAICompatibleLLM(BaseLLM):
    def __init__(self, model: str, base_url: str | None, api_key: str, temperature: float,
                 max_tokens: int, seed: int | None, max_retries: int = 3, timeout_s: int = 120):
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMError("Instala la librería: pip install openai") from exc
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_s)
        self._seed = seed
        self._max_retries = max_retries

    def _complete(self, system: str, user: str) -> LLMResponse:
        def call() -> LLMResponse:
            kwargs = dict(model=self.model, temperature=self.temperature, max_tokens=self.max_tokens,
                          messages=[{"role": "system", "content": system},
                                    {"role": "user", "content": user}])
            if self._seed is not None:
                kwargs["seed"] = self._seed  # no todos los proveedores lo respetan
            r = self._client.chat.completions.create(**kwargs)
            usage = r.usage
            return LLMResponse(text=r.choices[0].message.content or "",
                               input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                               output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                               latency_s=0.0, model=r.model or self.model)
        return _with_retries(call, self._max_retries)


class AnthropicLLM(BaseLLM):
    def __init__(self, model: str, api_key: str, temperature: float, max_tokens: int,
                 max_retries: int = 3, timeout_s: int = 120):
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError("Instala la librería: pip install anthropic") from exc
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_s)
        self._max_retries = max_retries

    def _complete(self, system: str, user: str) -> LLMResponse:
        def call() -> LLMResponse:
            r = self._client.messages.create(model=self.model, system=system,
                                             temperature=self.temperature, max_tokens=self.max_tokens,
                                             messages=[{"role": "user", "content": user}])
            text = "".join(getattr(b, "text", "") for b in r.content)
            return LLMResponse(text=text, input_tokens=r.usage.input_tokens,
                               output_tokens=r.usage.output_tokens, latency_s=0.0, model=r.model)
        return _with_retries(call, self._max_retries)


class ClaudeCLILLM(BaseLLM):
    """EXPERIMENTAL y NO PROBADO: usa el comando `claude -p` (Claude Code) con tu plan.

    Limitaciones: no se puede fijar la temperatura (incumple RNF-2) y el uso
    cuenta contra los límites de tu suscripción. Úsalo solo para desarrollo.
    """

    def __init__(self, model: str, timeout_s: int = 300):
        super().__init__(model=model, temperature=float("nan"))
        self._exe = shutil.which("claude")
        if not self._exe:
            raise LLMError("No se encontró el comando `claude`. Instala Claude Code primero.")
        self._timeout = timeout_s

    def _complete(self, system: str, user: str) -> LLMResponse:
        cmd = [self._exe, "-p", "--output-format", "json", "--model", self.model,
               "--system-prompt", system]
        try:
            out = subprocess.run(cmd, input=user, capture_output=True, text=True,
                                 encoding="utf-8", timeout=self._timeout)
        except subprocess.TimeoutExpired as exc:
            raise LLMError("`claude -p` excedió el tiempo límite") from exc
        if out.returncode != 0:
            raise LLMError(f"`claude -p` falló: {out.stderr[:500]}")
        try:
            data = json.loads(out.stdout)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Salida no JSON de `claude -p`: {out.stdout[:300]}") from exc
        usage = data.get("usage", {}) or {}
        return LLMResponse(text=data.get("result", ""), input_tokens=usage.get("input_tokens", 0),
                           output_tokens=usage.get("output_tokens", 0), latency_s=0.0, model=self.model)


def create_llm(cfg: dict, mock_responder=None) -> BaseLLM:
    """Fábrica: crea el cliente según config.yaml."""
    c = cfg["llm"]
    provider = c["provider"]
    if provider == "mock":
        if mock_responder is None:
            raise LLMError("Con provider=mock debes pasar `mock_responder` (respuestas simuladas).")
        return MockLLM(mock_responder, model=c.get("model", "mock-model"))
    if provider in ("openai_compatible", "anthropic"):
        key = os.environ.get(c.get("api_key_env", "LLM_API_KEY"), "")
        if not key:
            raise LLMError(f"Falta la clave: define la variable de entorno {c.get('api_key_env')}")
        if provider == "anthropic":
            return AnthropicLLM(c["model"], key, c["temperature"], c["max_tokens"],
                                c.get("max_retries", 3), c.get("request_timeout_s", 120))
        return OpenAICompatibleLLM(c["model"], c.get("base_url"), key, c["temperature"],
                                   c["max_tokens"], cfg.get("seed"), c.get("max_retries", 3),
                                   c.get("request_timeout_s", 120))
    if provider == "claude_cli":
        return ClaudeCLILLM(c["model"], c.get("request_timeout_s", 300))
    raise LLMError(f"Proveedor desconocido: {provider}")
