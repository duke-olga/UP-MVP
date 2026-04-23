from dataclasses import dataclass

import numpy as np

from backend.models import Competency, RecommendedElement
from backend.modules.recommendation.embedder import embed

# Cache per program_code: list of element ids + their embedding matrix.
# Invalidated when the element list changes (different ids).
_corpus_cache: dict[str, tuple[list[int], np.ndarray]] = {}

# Global competency corpus cache (competencies are not program-specific).
_competency_corpus_cache: tuple[list[int], np.ndarray] | None = None


@dataclass
class RankedElement:
    element: RecommendedElement
    score: float


@dataclass
class RankedCompetency:
    competency: Competency
    score: float


def _build_corpus(program_code: str, elements: list[RecommendedElement]) -> tuple[list[int], np.ndarray]:
    ids = [e.id for e in elements]
    cached = _corpus_cache.get(program_code)
    if cached is not None and cached[0] == ids:
        return cached
    texts = [e.name for e in elements]
    vecs = embed(texts)
    _corpus_cache[program_code] = (ids, vecs)
    return ids, vecs


def _build_competency_corpus(competencies: list[Competency]) -> tuple[list[int], np.ndarray]:
    global _competency_corpus_cache
    ids = [c.id for c in competencies]
    if _competency_corpus_cache is not None and _competency_corpus_cache[0] == ids:
        return _competency_corpus_cache
    texts = [f"{c.code}: {c.name}. {c.description or ''}" for c in competencies]
    vecs = embed(texts)
    _competency_corpus_cache = (ids, vecs)
    return ids, vecs


def semantic_search(
    query: str,
    elements: list[RecommendedElement],
    top_k: int = 10,
) -> list[RankedElement]:
    if not elements:
        return []

    program_code = elements[0].program_code or "__unknown__"
    ids, corpus_vecs = _build_corpus(program_code, elements)

    query_vec: np.ndarray = embed([query])[0]
    scores: np.ndarray = corpus_vecs @ query_vec  # cosine similarity (both normalised)

    id_to_element = {e.id: e for e in elements}
    ranked = sorted(zip(ids, scores.tolist()), key=lambda x: x[1], reverse=True)

    return [
        RankedElement(element=id_to_element[eid], score=score)
        for eid, score in ranked[:top_k]
        if eid in id_to_element
    ]


def suggest_competencies(
    discipline_name: str,
    competencies: list[Competency],
    top_k: int = 10,
) -> list[RankedCompetency]:
    if not competencies:
        return []

    ids, corpus_vecs = _build_competency_corpus(competencies)

    query_vec: np.ndarray = embed([discipline_name])[0]
    scores: np.ndarray = corpus_vecs @ query_vec  # cosine similarity (both normalised)

    id_to_comp = {c.id: c for c in competencies}
    ranked = sorted(zip(ids, scores.tolist()), key=lambda x: x[1], reverse=True)

    return [
        RankedCompetency(competency=id_to_comp[cid], score=score)
        for cid, score in ranked[:top_k]
        if cid in id_to_comp
    ]


def invalidate_cache(program_code: str | None = None) -> None:
    global _competency_corpus_cache
    if program_code:
        _corpus_cache.pop(program_code, None)
    else:
        _corpus_cache.clear()
        _competency_corpus_cache = None
