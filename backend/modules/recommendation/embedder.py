import logging

import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        logger.info("Loading semantic model %s (first request, may take a moment)…", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Semantic model loaded.")
        return _model
    except Exception as exc:
        logger.warning("Failed to load semantic model: %s", exc)
        raise


def embed(texts: list[str]) -> np.ndarray:
    """Return L2-normalised embeddings; cosine similarity = dot product."""
    return _get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)


def is_available() -> bool:
    try:
        _get_model()
        return True
    except Exception:
        return False
