"""Paso 2: cliente LLM (con el simulado; los reales requieren clave)."""
import pytest

from core.llm_client import LLMError, MockLLM, create_llm


def test_mock_returns_in_order_and_counts():
    llm = MockLLM(["uno", "dos"])
    assert llm.complete("s", "u").text == "uno"
    assert llm.complete("s", "u").text == "dos"
    assert llm.calls == 2
    assert llm.total_input_tokens > 0


def test_mock_without_responses_raises():
    with pytest.raises(LLMError):
        MockLLM([]).complete("s", "u")


def test_empty_answer_is_an_error():
    with pytest.raises(LLMError):
        MockLLM(["   "]).complete("s", "u")


def test_missing_api_key_gives_clear_error(cfg, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    c = {**cfg, "llm": {**cfg["llm"], "provider": "openai_compatible"}}
    with pytest.raises(LLMError, match="clave"):
        create_llm(c)
