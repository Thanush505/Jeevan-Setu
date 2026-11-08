"""
chatbot/rag/embedding_service.py — Semantic Embedding Service for Jeevan Setu RAG.

Uses Sentence Transformers (`sentence-transformers/all-MiniLM-L6-v2`) to generate
384-dimensional dense vector embeddings for document indexing and query retrieval.
"""

import logging
import math
import threading
from typing import List

logger = logging.getLogger("jeevan_setu.rag.embedding_service")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EXPECTED_EMBEDDING_DIMENSION = 384

_model = None
_model_lock = threading.Lock()


def _extract_model_dimension(model) -> int:
    """Compatibility helper for retrieving embedding dimension across SentenceTransformers versions."""
    if hasattr(model, "get_embedding_dimension"):
        return int(model.get_embedding_dimension())
    return int(model.get_sentence_embedding_dimension())


def _get_model():
    """
    Lazily load and cache the SentenceTransformer model instance.
    Ensures the model is not downloaded or loaded when the module is merely imported,
    and is loaded only once across repeated calls.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:
                    logger.error("sentence-transformers is not installed: %s", exc)
                    raise RuntimeError(
                        "The 'sentence-transformers' package is required for embedding generation."
                    ) from exc

                logger.info("Loading SentenceTransformer model: %s", MODEL_NAME)
                _model = SentenceTransformer(MODEL_NAME)
                logger.info(
                    "Successfully loaded SentenceTransformer model '%s' (dimension=%s)",
                    MODEL_NAME,
                    _extract_model_dimension(_model),
                )
    return _model


def get_embedding_model():
    """
    Return the lazily loaded, cached SentenceTransformer model instance
    (`sentence-transformers/all-MiniLM-L6-v2`).

    Ensures the model is loaded at most once per process and reused across
    all single-text and batch embedding requests.
    """
    return _get_model()


def _validate_single_text(text: str) -> str:
    """Validate that input is a non-empty string and return its stripped form."""
    if not isinstance(text, str):
        raise ValueError(f"Expected 'text' to be a str, got {type(text).__name__}.")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Input 'text' must be a non-empty, non-whitespace string.")
    return cleaned


def get_embedding(text: str) -> List[float]:
    """
    Generate a 384-dimensional semantic embedding for a single non-empty string.

    Args:
        text: Non-empty string to embed.

    Returns:
        List of 384 float values.

    Raises:
        ValueError: If `text` is not a non-empty string.
    """
    cleaned_text = _validate_single_text(text)
    model = _get_model()

    vector = model.encode(
        cleaned_text,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    embedding = [float(val) for val in vector.tolist()]

    if len(embedding) != EXPECTED_EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"Unexpected embedding dimension {len(embedding)}; expected {EXPECTED_EMBEDDING_DIMENSION}."
        )
    if not all(math.isfinite(val) for val in embedding):
        raise RuntimeError("Generated embedding contains non-finite values (NaN or Inf).")

    return embedding


def get_embeddings(texts: list[str]) -> List[List[float]]:
    """
    Generate 384-dimensional semantic embeddings for a batch of non-empty strings.

    Args:
        texts: Non-empty list of non-empty strings.

    Returns:
        List of 384-dimensional float vectors corresponding to each input string.

    Raises:
        ValueError: If `texts` is not a list/tuple, is empty, or contains invalid/empty strings.
    """
    if not isinstance(texts, (list, tuple)):
        raise ValueError(f"Expected 'texts' to be a list of strings, got {type(texts).__name__}.")
    if len(texts) == 0:
        raise ValueError("Input 'texts' must be a non-empty list of non-empty strings.")

    cleaned_texts: List[str] = []
    for idx, item in enumerate(texts):
        if not isinstance(item, str):
            raise ValueError(
                f"Element at index {idx} in 'texts' must be a str, got {type(item).__name__}."
            )
        stripped = item.strip()
        if not stripped:
            raise ValueError(
                f"Element at index {idx} in 'texts' must be a non-empty, non-whitespace string."
            )
        cleaned_texts.append(stripped)

    model = _get_model()
    logger.debug("Generating batch embeddings for %d texts using '%s'", len(cleaned_texts), MODEL_NAME)

    vectors = model.encode(
        cleaned_texts,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    embeddings = [[float(val) for val in row] for row in vectors.tolist()]

    for idx, emb in enumerate(embeddings):
        if len(emb) != EXPECTED_EMBEDDING_DIMENSION:
            raise RuntimeError(
                f"Unexpected embedding dimension {len(emb)} at index {idx}; expected {EXPECTED_EMBEDDING_DIMENSION}."
            )
        if not all(math.isfinite(val) for val in emb):
            raise RuntimeError(f"Generated embedding at index {idx} contains non-finite values.")

    return embeddings


def get_embedding_dimension() -> int:
    """
    Return the actual embedding dimension of the configured SentenceTransformer model.

    Returns:
        int: Embedding dimension (expected: 384).
    """
    model = _get_model()
    return _extract_model_dimension(model)
