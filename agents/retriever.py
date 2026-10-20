"""Agente Recuperador (RF-2): embeddings + RAG sobre el corpus de Mathlib.

Entrada: un subobjetivo. Salida: los k lemas más parecidos con su firma Lean
y su puntaje de similitud coseno. No usa LLM (no consume llamadas de RNF-3).
"""
from __future__ import annotations

import time

from agents.base import StepContext
from core.run_logger import RunLogger
from core.schemas import validate
from retrieval.embedder import lemma_to_text
from retrieval.vector_index import VectorIndex


class Retriever:
    name = "retriever"

    def __init__(self, index: VectorIndex, embedder, top_k: int = 8, logger: RunLogger | None = None):
        if embedder.name != index.embedder_name:
            raise ValueError(f"El índice se construyó con '{index.embedder_name}' pero el embedder actual "
                             f"es '{embedder.name}'. Reconstruye el índice (RNF-2).")
        self.index = index
        self.embedder = embedder
        self.top_k = top_k
        self.logger = logger

    def retrieve(self, subgoal: dict, ctx: StepContext) -> dict:
        start = time.perf_counter()
        query = lemma_to_text("", f"{subgoal.get('informal', '')} {subgoal['lean_decl']}")
        qvec = self.embedder.encode([query])[0]
        hits = self.index.search(qvec, self.top_k)
        lemmas = [{"name": self.index.lemmas[i]["name"], "statement": self.index.lemmas[i]["statement"],
                   "module": self.index.lemmas[i].get("module"), "score": round(score, 4)}
                  for i, score in hits]
        out = validate("retriever_output", {"lemmas": lemmas, "query_embedding_dim": int(qvec.shape[0])})
        if self.logger:
            self.logger.log_agent_step(problem_id=ctx.problem_id, agent=self.name, attempt=ctx.attempt,
                                       subgoal_id=ctx.subgoal_id, decision=f"retrieved_{len(lemmas)}",
                                       latency_s=time.perf_counter() - start,
                                       details={"top": [l["name"] for l in lemmas[:5]]})
        return out
