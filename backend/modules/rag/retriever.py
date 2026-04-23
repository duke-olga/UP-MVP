from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.models import Competency, RecommendedElement
from backend.modules.rag.chunker import Chunk, build_chunks
from backend.modules.recommendation.embedder import embed


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float


# Cache: program_code → (element_count, competency_count, chunks, vecs)
# Invalidated automatically when element or competency counts change (e.g., after re-import).
_rag_cache: dict[str, tuple[int, int, list[Chunk], np.ndarray]] = {}


def _build_corpus(
    program_code: str,
    elements: list[RecommendedElement],
    competencies: list[Competency],
) -> tuple[list[Chunk], np.ndarray]:
    el_count = len(elements)
    co_count = len(competencies)

    cached = _rag_cache.get(program_code)
    if cached is not None:
        c_el, c_co, cached_chunks, cached_vecs = cached
        if c_el == el_count and c_co == co_count:
            return cached_chunks, cached_vecs

    chunks = build_chunks(program_code, elements, competencies)
    vecs = embed([c.text for c in chunks])
    _rag_cache[program_code] = (el_count, co_count, chunks, vecs)
    return chunks, vecs


def retrieve(
    query: str,
    program_code: str,
    elements: list[RecommendedElement],
    competencies: list[Competency],
    top_k: int = 8,
) -> list[RetrievedChunk]:
    chunks, corpus_vecs = _build_corpus(program_code, elements, competencies)
    if not chunks:
        return []

    query_vec: np.ndarray = embed([query])[0]
    scores: np.ndarray = corpus_vecs @ query_vec  # cosine similarity (both L2-normalised)

    ranked = sorted(enumerate(scores.tolist()), key=lambda x: x[1], reverse=True)
    return [RetrievedChunk(chunk=chunks[i], score=score) for i, score in ranked[:top_k]]


def invalidate_cache(program_code: str | None = None) -> None:
    if program_code:
        _rag_cache.pop(program_code, None)
    else:
        _rag_cache.clear()
