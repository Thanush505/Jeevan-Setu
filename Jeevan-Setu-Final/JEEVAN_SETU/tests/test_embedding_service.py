"""
tests/test_embedding_service.py — Comprehensive pytest suite for Jeevan Setu RAG `embedding_service.py`.

Covers all 10 required test scenarios using synthetic non-patient content only:
1. Single-text embedding (`get_embedding`).
2. Batch embedding (`get_embeddings`).
3. Embedding dimension (`get_embedding_dimension` == 384).
4. Empty input handling (empty string, whitespace-only string, empty batch).
5. Invalid input handling (None, integers, dicts, invalid elements inside a batch).
6. Multiple texts preserve output order.
7. Vector length is 384 (`EXPECTED_EMBEDDING_DIMENSION`).
8. All vector values are finite floats (no NaN or Inf) and Unicode / clinical terminology is supported.
9. Model caching (`get_embedding_model` returns the exact same cached instance across calls).
10. Compatibility with `document_processor.py` output without mutating chunk metadata.
"""

import copy
import math
from typing import Dict, Any, List

import pytest

import chatbot.rag.embedding_service as es
from chatbot.rag.embedding_service import (
    EXPECTED_EMBEDDING_DIMENSION,
    MODEL_NAME,
    get_embedding,
    get_embedding_dimension,
    get_embedding_model,
    get_embeddings,
)
from chatbot.rag.document_processor import process_documents


def _cosine_sim(vec_a: List[float], vec_b: List[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def test_01_single_text_embedding():
    """1. Verify `get_embedding(text)` returns a list of 384 floats for a single non-empty string."""
    text = "Continuous noninvasive blood pressure and pulse oximetry monitoring in high-dependency care."
    vec = get_embedding(text)

    assert isinstance(vec, list)
    assert len(vec) == 384
    assert all(isinstance(v, float) for v in vec)


def test_02_batch_embedding():
    """2. Verify `get_embeddings(texts)` generates a batch of 384-d vectors in a single call."""
    texts = [
        "Mechanical ventilation weaning protocol and spontaneous breathing trial criteria.",
        "Early Warning Score (NEWS2) escalation workflow for acute clinical deterioration.",
        "Standard Operating Procedure for ICU to HDU step-down bed allocation.",
    ]
    batch_vecs = get_embeddings(texts)

    assert isinstance(batch_vecs, list)
    assert len(batch_vecs) == 3
    for vec in batch_vecs:
        assert isinstance(vec, list)
        assert len(vec) == 384
        assert all(isinstance(v, float) for v in vec)


def test_03_embedding_dimension():
    """3. Verify `get_embedding_dimension()` returns 384 and matches `MODEL_NAME` configuration."""
    assert MODEL_NAME == "sentence-transformers/all-MiniLM-L6-v2"
    assert EXPECTED_EMBEDDING_DIMENSION == 384
    assert get_embedding_dimension() == 384


def test_04_empty_input():
    """4. Verify empty strings, whitespace-only strings, and empty batch lists raise `ValueError`."""
    with pytest.raises(ValueError, match="non-empty"):
        get_embedding("")

    with pytest.raises(ValueError, match="non-empty"):
        get_embedding("   \n\t\r  ")

    with pytest.raises(ValueError, match="non-empty"):
        get_embeddings([])

    with pytest.raises(ValueError, match="non-empty"):
        get_embeddings(["Valid first text", "   \t\n  "])


def test_05_invalid_input():
    """5. Verify non-string inputs and malformed batch inputs raise `ValueError`."""
    for invalid_single in (None, 123, 45.6, ["list_instead_of_str"], {"text": "dict"}):
        with pytest.raises(ValueError):
            get_embedding(invalid_single)  # type: ignore[arg-type]

    for invalid_batch in (None, "a single string instead of a list", 999, {"a": "b"}):
        with pytest.raises(ValueError):
            get_embeddings(invalid_batch)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        get_embeddings(["Valid text", None])  # type: ignore[list-item]

    with pytest.raises(ValueError):
        get_embeddings(["Valid text", 42])  # type: ignore[list-item]


def test_06_multiple_texts_preserve_output_order():
    """6. Verify batch embeddings strictly preserve the exact input order of texts."""
    distinct_texts = [
        "Arterial blood gas interpretation: pH 7.38, PaCO2 40 mmHg, HCO3 24 mEq/L.",
        "Solar observatory telescopes capture high-resolution images of coronal loops.",
        "Hospital pharmacy cold-chain storage guidelines for temperature-sensitive biologics.",
        "Deep-sea autonomous submersibles map hydrothermal vents along mid-oceanic ridges.",
    ]

    batch_vecs = get_embeddings(distinct_texts)
    single_vecs = [get_embedding(t) for t in distinct_texts]

    assert len(batch_vecs) == len(distinct_texts)
    for i in range(len(distinct_texts)):
        # Each batch vector at index `i` must match its corresponding single-text vector (~1.0 cosine similarity)
        self_sim = _cosine_sim(batch_vecs[i], single_vecs[i])
        assert self_sim > 0.9999, f"Order mismatch at index {i}: cosine similarity={self_sim}"

        # And must be clearly distinct from unrelated entries in the batch
        other_idx = (i + 1) % len(distinct_texts)
        cross_sim = _cosine_sim(batch_vecs[i], single_vecs[other_idx])
        assert self_sim > cross_sim + 0.3


def test_07_vector_length_is_384():
    """7. Verify every generated single and batch vector has length 384 regardless of input text length."""
    short_text = "SpO2 >= 94%"
    long_text = " ".join(
        [
            f"Clause {i}: Verify hemodynamic stability, respiratory rate 12-20 breaths/min, "
            f"and absence of vasopressor escalation prior to High Dependency Unit transfer."
            for i in range(1, 35)
        ]
    )

    vec_short = get_embedding(short_text)
    vec_long = get_embedding(long_text)
    vec_batch = get_embeddings([short_text, long_text])

    assert len(vec_short) == 384
    assert len(vec_long) == 384
    assert [len(v) for v in vec_batch] == [384, 384]


def test_08_all_vector_values_are_finite_and_unicode_clinical_supported():
    """8. Verify all 384 values are finite floats (`math.isfinite`) including Unicode clinical symbols."""
    clinical_unicode_texts = [
        "Temperature: 36.8 °C ± 0.4 °C; SpO₂ ≥ 95%; PaO₂/FiO₂ ratio > 300 mmHg; Lactate ≤ 1.8 mmol/L.",
        "Infusion rate: Norepinephrine 0.05–0.15 µg/kg/min via central venous catheter (ΔMAP +12 mmHg).",
    ]

    single_vec = get_embedding(clinical_unicode_texts[0])
    batch_vecs = get_embeddings(clinical_unicode_texts)

    assert all(isinstance(x, float) and math.isfinite(x) for x in single_vec)
    for vec in batch_vecs:
        assert all(isinstance(x, float) and math.isfinite(x) for x in vec)


def test_09_model_caching():
    """9. Verify `get_embedding_model()` lazily caches and reuses the exact same model instance."""
    model_1 = get_embedding_model()
    model_2 = get_embedding_model()
    assert model_1 is not None
    assert model_1 is model_2
    assert es._model is model_1

    # Subsequent embedding calls must reuse the same cached model object without reloading
    _ = get_embedding("Verify cached model instance reuse.")
    _ = get_embeddings(["Batch item one.", "Batch item two."])
    assert get_embedding_model() is model_1


def test_10_compatibility_with_document_processor_output():
    """10. Verify embeddings can be generated directly from `document_processor.py` chunks without modifying chunk metadata."""
    loaded_docs: List[Dict[str, Any]] = [
        {
            "document_id": "doc_clinical_sop_p1_001",
            "source": "clinical_protocols/hdu_monitoring_sop.pdf",
            "category": "clinical_protocols",
            "file_type": "pdf",
            "page_number": 1,
            "ocr_required": False,
            "image_assets": [
                {
                    "image_id": "img_hdu_monitoring_p1_1",
                    "source_document": "clinical_protocols/hdu_monitoring_sop.pdf",
                    "document_id": "doc_clinical_sop_p1_001",
                    "page_number": 1,
                    "image_format": "png",
                    "file_size": 1024,
                    "asset_path": "_extracted_assets/hdu_monitoring_p1_1.png",
                }
            ],
            "content": (
                "# HDU Telemetry Protocol\n\n"
                "Record heart rate, invasive or noninvasive blood pressure, respiratory rate, "
                "and oxygen saturation every 30 minutes for the first 4 hours post-transfer.\n\n"
                "Escalate immediately if NEWS2 score increases by 2 or more points."
            ),
        }
    ]

    chunks = process_documents(loaded_docs, chunk_size=40, overlap=8)
    assert len(chunks) >= 2
    chunks_snapshot = copy.deepcopy(chunks)

    # Generate single and batch embeddings from processed chunk content
    single_emb = get_embedding(chunks[0]["content"])
    batch_embs = get_embeddings([c["content"] for c in chunks])

    assert len(single_emb) == 384
    assert len(batch_embs) == len(chunks)
    assert all(len(e) == 384 for e in batch_embs)

    # Verify chunk dictionaries and their metadata were not mutated
    assert chunks == chunks_snapshot

