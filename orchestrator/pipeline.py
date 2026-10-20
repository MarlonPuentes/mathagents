"""Construye el sistema según la configuración de ablación (sección 8.2 del PDF).

| nombre      | RAG | Crítico | k_max            |
|-------------|-----|---------|------------------|
| no_rag      | no  | sí      | config (3 a 5)   |
| no_critic   | sí  | no      | 1                |
| full        | sí  | sí      | config (3 a 5)   |
baseline_a y baseline_b están en orchestrator/baselines.py.
"""
from __future__ import annotations

from agents.retriever import Retriever
from agents.verifier import LeanVerifier
from core.config import resolve_path
from core.llm_client import BaseLLM
from core.run_logger import RunLogger
from orchestrator.graph import PipelineOptions, ProofOrchestrator

CONFIGURATIONS = ["baseline_a", "baseline_b", "no_rag", "no_critic", "full"]


def options_for(configuration: str, cfg: dict) -> PipelineOptions:
    o = cfg["orchestrator"]
    base = dict(k_max=o["k_max"], max_replans=o["max_replans"], llm_call_budget=o["llm_call_budget"])
    if configuration == "full":
        return PipelineOptions(use_rag=True, use_critic=True, **base)
    if configuration == "no_rag":
        return PipelineOptions(use_rag=False, use_critic=True, **base)
    if configuration == "no_critic":
        base.update(k_max=1, max_replans=0)
        return PipelineOptions(use_rag=True, use_critic=False, **base)
    raise ValueError(f"'{configuration}' no es una configuración multiagente. Opciones: no_rag, no_critic, full")


def build_retriever(cfg: dict, logger: RunLogger | None = None, embedder=None, index=None) -> Retriever:
    from retrieval.embedder import create_embedder
    from retrieval.vector_index import VectorIndex
    embedder = embedder or create_embedder(cfg)
    index = index or VectorIndex.load(resolve_path(cfg["retrieval"]["index_dir"]))
    return Retriever(index, embedder, cfg["retrieval"]["top_k"], logger)


def build_orchestrator(configuration: str, cfg: dict, llm: BaseLLM, verifier: LeanVerifier,
                       logger: RunLogger | None = None, retriever: Retriever | None = None) -> ProofOrchestrator:
    opts = options_for(configuration, cfg)
    if opts.use_rag and retriever is None:
        retriever = build_retriever(cfg, logger)
    a = cfg["agents"]
    return ProofOrchestrator(llm, verifier, retriever if opts.use_rag else None, opts, logger,
                             max_subgoals=a["max_subgoals"], generator_samples=a["generator_samples"],
                             critic_uses_llm=a["critic_uses_llm"])
