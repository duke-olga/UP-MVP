from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from backend.models import Competency, RecommendedElement
from backend.modules.rag.chunker import Chunk, build_chunks
from backend.modules.rag.fgos_parser import load_fgos_chunks
from backend.modules.recommendation.embedder import embed

_log = logging.getLogger(__name__)

_MIN_SCORE = 0.25  # discard chunks with cosine similarity below this threshold


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float


# Cache: program_code → (element_count, competency_count, norms_count, fgos_chunks, fgos_vecs, db_chunks, db_vecs)
_rag_cache: dict[str, tuple[int, int, int, list[Chunk], np.ndarray, list[Chunk], np.ndarray]] = {}


def _build_corpus(
    program_code: str,
    elements: list[RecommendedElement],
    competencies: list[Competency],
    norms: dict[str, float] | None = None,
) -> tuple[list[Chunk], np.ndarray, list[Chunk], np.ndarray]:
    """Return (fgos_chunks, fgos_vecs, db_chunks, db_vecs) — two separate corpora."""
    el_count = len(elements)
    co_count = len(competencies)
    norms_count = len(norms) if norms else 0

    cached = _rag_cache.get(program_code)
    if cached is not None:
        c_el, c_co, c_no, fc, fv, dc, dv = cached
        if c_el == el_count and c_co == co_count and c_no == norms_count:
            return fc, fv, dc, dv

    fgos_chunks = load_fgos_chunks(program_code)
    all_db_chunks = build_chunks(program_code, elements, competencies, norms=norms)

    # Chunks built from DB but tagged source_type="fgos" (e.g. competency summaries)
    # belong in the FGOS pool so they are prioritised over discipline elements.
    extra_fgos = [c for c in all_db_chunks if c.source_type == "fgos"]
    db_chunks = [c for c in all_db_chunks if c.source_type != "fgos"]
    fgos_chunks = fgos_chunks + extra_fgos

    fgos_vecs = embed([c.text for c in fgos_chunks]) if fgos_chunks else np.empty((0, 384))
    db_vecs = embed([c.text for c in db_chunks]) if db_chunks else np.empty((0, 384))

    _rag_cache[program_code] = (el_count, co_count, norms_count, fgos_chunks, fgos_vecs, db_chunks, db_vecs)
    return fgos_chunks, fgos_vecs, db_chunks, db_vecs


def _top_k_from(
    chunks: list[Chunk],
    vecs: np.ndarray,
    query_vec: np.ndarray,
    k: int,
) -> list[RetrievedChunk]:
    if not chunks or vecs.shape[0] == 0:
        return []
    scores: np.ndarray = vecs @ query_vec
    ranked = sorted(enumerate(scores.tolist()), key=lambda x: x[1], reverse=True)
    results = []
    for i, score in ranked[:k]:
        if score < _MIN_SCORE:
            break
        results.append(RetrievedChunk(chunk=chunks[i], score=score))
    return results


def retrieve(
    query: str,
    program_code: str,
    elements: list[RecommendedElement],
    competencies: list[Competency],
    top_k: int = 8,
    fgos_k: int | None = None,
    db_k: int | None = None,
    norms: dict[str, float] | None = None,
) -> list[RetrievedChunk]:
    """Retrieve top chunks: FGOS docs first, then DB records.

    fgos_k defaults to ceil(top_k * 0.6), db_k to the remainder.
    FGOS results always come before DB results so the LLM sees authoritative
    document text near the start of the context window.
    """
    fgos_chunks, fgos_vecs, db_chunks, db_vecs = _build_corpus(program_code, elements, competencies, norms=norms)

    if fgos_k is None:
        fgos_k = max(1, round(top_k * 0.7))
    if db_k is None:
        db_k = max(0, top_k - fgos_k)

    query_vec: np.ndarray = embed([query])[0]

    fgos_results = _top_k_from(fgos_chunks, fgos_vecs, query_vec, fgos_k)
    db_results = _top_k_from(db_chunks, db_vecs, query_vec, db_k)

    combined = fgos_results + db_results
    _log.debug(
        "RAG retrieve [%s] fgos=%d db=%d | chunks: %s",
        program_code,
        len(fgos_results),
        len(db_results),
        ", ".join(f"{r.chunk.source_label}({r.score:.2f})" for r in combined),
    )
    return combined


def invalidate_cache(program_code: str | None = None) -> None:
    if program_code:
        _rag_cache.pop(program_code, None)
    else:
        _rag_cache.clear()
