"""Paso 9: embeddings + índice + Recuperador (RF-2)."""
import json

import numpy as np
import pytest

from agents.base import StepContext
from agents.retriever import Retriever
from core.config import resolve_path
from retrieval.embedder import HashingEmbedder, lemma_to_text
from retrieval.vector_index import VectorIndex

CORPUS = [
    {"name": "add_sq", "statement": "(a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2", "module": "m"},
    {"name": "mul_pos", "statement": "0 < a → 0 < b → 0 < a * b", "module": "m"},
    {"name": "sq_nonneg", "statement": "0 ≤ a ^ 2", "module": "m"},
    {"name": "two_mul", "statement": "2 * n = n + n", "module": "m"},
]


def test_embeddings_are_normalized_and_deterministic():
    e = HashingEmbedder()
    v1, v2 = e.encode(["hola mundo"]), e.encode(["hola mundo"])
    assert np.allclose(v1, v2) and np.isclose(np.linalg.norm(v1), 1.0)


def test_index_save_load_roundtrip(tmp_path):
    e = HashingEmbedder()
    idx = VectorIndex.build(CORPUS, e, lemma_to_text)
    idx.save(tmp_path)
    loaded = VectorIndex.load(tmp_path)
    assert loaded.lemmas == CORPUS and loaded.embedder_name == e.name


def test_query_with_lemma_text_finds_itself():
    e = HashingEmbedder()
    idx = VectorIndex.build(CORPUS, e, lemma_to_text)
    for i, lem in enumerate(CORPUS):
        top = idx.search(e.encode([lemma_to_text(lem["name"], lem["statement"])])[0], 1)
        assert top[0][0] == i


def test_retriever_contract_and_mismatch_protection():
    e = HashingEmbedder()
    idx = VectorIndex.build(CORPUS, e, lemma_to_text)
    out = Retriever(idx, e, top_k=2).retrieve({"id": "s", "informal": "square of a sum",
                                              "lean_decl": "theorem s (a b : ℤ) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2"},
                                             StepContext())
    assert len(out["lemmas"]) == 2 and out["query_embedding_dim"] == e.dim
    assert out["lemmas"][0]["name"] == "add_sq"
    idx.embedder_name = "otro-modelo"
    with pytest.raises(ValueError):
        Retriever(idx, e)


def test_reference_set_file_is_well_formed():
    rows = [json.loads(l) for l in open(resolve_path("data/retrieval_reference.jsonl"), encoding="utf-8")]
    assert rows and all({"query", "expected"} <= set(r) for r in rows)
