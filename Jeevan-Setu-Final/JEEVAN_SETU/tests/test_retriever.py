"""
tests/test_retriever.py — Comprehensive Pytest Suite for Jeevan Setu RAG `retriever.py`.

Covers all 18 required test scenarios using temporary ChromaDB directories (`tmp_path`)
and synthetic non-patient documents:
1. Query embedding integration (`embed_query` calls `get_embedding` and validates 384 finite floats).
2. Basic semantic search (`retrieve_relevant_chunks`).
3. Top-k limits.
4. Category filtering.
5. Document ID filtering (`retrieve_by_document_id` and `document_id` filter).
6. File-type filtering.
7. Document-version filtering.
8. Relevance threshold behavior (`min_relevance`).
9. Deterministic ordering.
10. Duplicate result removal.
11. Empty collection handling.
12. Invalid query handling.
13. Invalid filters handling.
14. Missing metadata handling (graceful defaults without fabricating page numbers).
15. Source and page traceability (`extract_source_references`).
16. Image reference preservation (`image_assets`).
17. Patient data isolation (rejects patient collections and filters out UHID-contaminated records).
18. ChromaDB error handling (returns `[]` safely when ChromaDB query raises an operational error).
"""

import math
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from chatbot.rag.document_processor import process_documents
from chatbot.rag.retriever import (
    DEFAULT_MIN_RELEVANCE_SCORE,
    distance_to_relevance_score,
    embed_query,
    extract_source_references,
    retrieve_by_document_id,
    retrieve_multiple_queries,
    retrieve_relevant_chunks,
    retrieve_with_filters,
)
from chatbot.rag.vector_store import VectorStore


@pytest.fixture
def populated_store(tmp_path: Path) -> VectorStore:
    """Create and populate an isolated temporary VectorStore with synthetic documents."""
    raw_docs: List[Dict[str, Any]] = [
        {
            "document_id": "DOC-NEWS2-001",
            "document_version": "1.0",
            "source": "approved_guidelines/news2_clinical_scoring.pdf",
            "category": "approved_guidelines",
            "file_type": "pdf",
            "page_number": 3,
            "ocr_required": False,
            "image_assets": [
                {
                    "image_id": "img_news2_chart_p3",
                    "document_id": "DOC-NEWS2-001",
                    "source_document": "approved_guidelines/news2_clinical_scoring.pdf",
                    "page_number": 3,
                    "image_format": "png",
                    "file_size": 2048,
                    "asset_path": "_extracted_assets/news2_chart_p3.png",
                }
            ],
            "content": (
                "National Early Warning Score (NEWS2) threshold of 7 or higher indicates high clinical risk "
                "and requires immediate intensive care review and continuous bedside telemetry."
            ),
        },
        {
            "document_id": "DOC-HDU-SOP-002",
            "document_version": "1.0",
            "source": "hospital_sops/icu_to_hdu_stepdown.docx",
            "category": "hospital_sops",
            "file_type": "docx",
            "page_number": None,
            "ocr_required": False,
            "image_assets": [],
            "content": (
                "Step-down transfer from Intensive Care Unit (ICU) to High Dependency Unit (HDU) "
                "requires stable spontaneous respiration, absence of vasopressor infusion, and SBAR handover."
            ),
        },
        {
            "document_id": "DOC-VENT-003",
            "document_version": "1.0",
            "source": "clinical_protocols/mechanical_ventilation.pdf",
            "category": "clinical_protocols",
            "file_type": "pdf",
            "page_number": 11,
            "ocr_required": False,
            "image_assets": [],
            "content": (
                "Lung-protective mechanical ventilation protocol v1.0: target tidal volume 6 mL/kg "
                "predicted body weight and plateau pressure <= 30 cmH2O."
            ),
        },
        {
            "document_id": "DOC-VENT-003",
            "document_version": "2.0",
            "source": "clinical_protocols/mechanical_ventilation.pdf",
            "category": "clinical_protocols",
            "file_type": "pdf",
            "page_number": 12,
            "ocr_required": False,
            "image_assets": [],
            "content": (
                "Lung-protective mechanical ventilation protocol v2.0: target tidal volume 4-6 mL/kg "
                "predicted body weight, plateau pressure <= 28 cmH2O, and driving pressure < 15 cmH2O."
            ),
        },
    ]

    chunks = process_documents(raw_docs)
    store = VectorStore(storage_dir=tmp_path / "chroma_retriever_test", sync_mysql=False)
    store.add_chunks(chunks, sync_mysql=False)
    return store


def test_01_query_embedding_integration():
    """1. Verify `embed_query` delegates to `get_embedding` and validates a 384-d finite float vector."""
    with patch("chatbot.rag.retriever.get_embedding", wraps=embed_query.__globals__["get_embedding"]) as spy_emb:
        vec = embed_query("What NEWS2 score requires immediate intensive care review?")
        spy_emb.assert_called_once()

    assert isinstance(vec, list)
    assert len(vec) == 384
    assert all(isinstance(x, float) and math.isfinite(x) for x in vec)


def test_02_basic_semantic_search(populated_store: VectorStore):
    """2. Verify `retrieve_relevant_chunks` returns the semantically matching chunk with expected fields."""
    results = retrieve_relevant_chunks(
        query="What NEWS2 score threshold indicates high clinical risk?",
        top_k=3,
        store=populated_store,
    )

    assert len(results) >= 1
    top = results[0]
    assert top["document_id"] == "DOC-NEWS2-001"
    assert "NEWS2" in top["content"]
    assert isinstance(top["relevance_score"], float)
    assert 0.0 <= top["relevance_score"] <= 1.0
    assert isinstance(top["distance"], float)


def test_03_top_k_limits(populated_store: VectorStore):
    """3. Verify `top_k` strictly caps the number of returned chunks."""
    res_1 = retrieve_relevant_chunks("clinical protocol ventilation and scoring", top_k=1, store=populated_store, min_relevance=0.0)
    res_2 = retrieve_relevant_chunks("clinical protocol ventilation and scoring", top_k=2, store=populated_store, min_relevance=0.0)
    res_all = retrieve_relevant_chunks("clinical protocol ventilation and scoring", top_k=10, store=populated_store, min_relevance=0.0)

    assert len(res_1) == 1
    assert len(res_2) == 2
    assert len(res_all) == 4


def test_04_category_filtering(populated_store: VectorStore):
    """4. Verify `category` filter restricts results to the specified knowledge-base category."""
    results = retrieve_with_filters(
        query="patient transfer and respiratory stability",
        category="hospital_sops",
        top_k=5,
        store=populated_store,
    )

    assert len(results) == 1
    assert results[0]["category"] == "hospital_sops"
    assert results[0]["document_id"] == "DOC-HDU-SOP-002"


def test_05_document_id_filtering(populated_store: VectorStore):
    """5. Verify `document_id` filter and `retrieve_by_document_id` return only chunks from that document."""
    results_filtered = retrieve_relevant_chunks(
        query="tidal volume and plateau pressure",
        document_id="DOC-VENT-003",
        top_k=5,
        store=populated_store,
    )
    assert len(results_filtered) == 2
    assert all(r["document_id"] == "DOC-VENT-003" for r in results_filtered)

    # Also test direct lookup via retrieve_by_document_id without a query
    direct_chunks = retrieve_by_document_id(
        document_id="DOC-HDU-SOP-002",
        store=populated_store,
    )
    assert len(direct_chunks) == 1
    assert direct_chunks[0]["document_id"] == "DOC-HDU-SOP-002"


def test_06_file_type_filtering(populated_store: VectorStore):
    """6. Verify `file_type` filter distinguishes between `pdf` and `docx` records."""
    docx_hits = retrieve_relevant_chunks(
        query="ICU to HDU step-down transfer criteria",
        file_type="docx",
        top_k=5,
        store=populated_store,
        min_relevance=0.0,
    )
    assert len(docx_hits) == 1
    assert docx_hits[0]["file_type"] == "docx"

    pdf_hits = retrieve_relevant_chunks(
        query="ICU to HDU step-down transfer criteria",
        file_type="pdf",
        top_k=5,
        store=populated_store,
        min_relevance=0.0,
    )
    assert len(pdf_hits) == 3
    assert all(r["file_type"] == "pdf" for r in pdf_hits)


def test_07_document_version_filtering(populated_store: VectorStore):
    """7. Verify `document_version` filter selects the exact requested version (`1.0` vs `2.0`)."""
    v1_hits = retrieve_relevant_chunks(
        query="lung protective mechanical ventilation plateau pressure",
        document_id="DOC-VENT-003",
        document_version="1.0",
        top_k=5,
        store=populated_store,
    )
    v2_hits = retrieve_relevant_chunks(
        query="lung protective mechanical ventilation plateau pressure",
        document_id="DOC-VENT-003",
        document_version="2.0",
        top_k=5,
        store=populated_store,
    )

    assert len(v1_hits) == 1
    assert v1_hits[0]["document_version"] == "1.0"
    assert "v1.0" in v1_hits[0]["content"]

    assert len(v2_hits) == 1
    assert v2_hits[0]["document_version"] == "2.0"
    assert "v2.0" in v2_hits[0]["content"]


def test_08_relevance_threshold_behavior(populated_store: VectorStore):
    """8. Verify `min_relevance` filters out chunks below the threshold."""
    assert DEFAULT_MIN_RELEVANCE_SCORE == 0.25
    assert distance_to_relevance_score(0.0, "cosine") == 1.0
    assert distance_to_relevance_score(1.0, "cosine") == 0.5
    assert distance_to_relevance_score(2.0, "cosine") == 0.0
    assert distance_to_relevance_score(None, "cosine") == 0.0

    # A strict threshold of 0.9999 should filter out non-identical queries
    strict_hits = retrieve_relevant_chunks(
        query="unrelated astronomical telescope mirror calibration",
        top_k=5,
        min_relevance=0.95,
        store=populated_store,
    )
    assert strict_hits == []


def test_09_deterministic_ordering(populated_store: VectorStore):
    """9. Verify repeated queries produce identical, deterministically ordered results sorted by descending relevance_score."""
    run_1 = retrieve_relevant_chunks(
        query="mechanical ventilation plateau pressure and NEWS2 score",
        top_k=4,
        min_relevance=0.0,
        store=populated_store,
    )
    run_2 = retrieve_relevant_chunks(
        query="mechanical ventilation plateau pressure and NEWS2 score",
        top_k=4,
        min_relevance=0.0,
        store=populated_store,
    )

    assert [r["chunk_id"] for r in run_1] == [r["chunk_id"] for r in run_2]
    scores = [r["relevance_score"] for r in run_1]
    assert scores == sorted(scores, reverse=True)


def test_10_duplicate_result_removal(tmp_path: Path):
    """10. Verify duplicate chunk contents or multi-query overlapping hits are deduplicated."""
    store = VectorStore(storage_dir=tmp_path / "dup_test", sync_mysql=False)
    # Insert two different IDs with the exact same text/content_hash
    identical_text = "Duplicate check: Verify infusion pump battery level before ICU transport."
    store.add_documents(
        documents=[identical_text, identical_text],
        metadatas=[
            {"document_id": "DOC-DUP-1", "source": "sop_a.md", "category": "hospital_sops"},
            {"document_id": "DOC-DUP-2", "source": "sop_b.md", "category": "hospital_sops"},
        ],
        ids=["dup_chunk_a", "dup_chunk_b"],
    )

    single_query_hits = retrieve_relevant_chunks(
        query="infusion pump battery level before ICU transport",
        top_k=5,
        store=store,
    )
    assert len(single_query_hits) == 1

    # Also verify retrieve_multiple_queries deduplicates overlapping hits across queries
    multi_hits = retrieve_multiple_queries(
        queries=[
            "infusion pump battery level",
            "ICU transport battery check",
        ],
        top_k_per_query=3,
        store=store,
    )
    assert len(multi_hits) == 1


def test_11_empty_collection(tmp_path: Path):
    """11. Verify searching an empty ChromaDB collection returns `[]` cleanly."""
    empty_store = VectorStore(storage_dir=tmp_path / "empty_chroma", sync_mysql=False)
    assert retrieve_relevant_chunks("any clinical protocol query", store=empty_store) == []
    assert retrieve_by_document_id("DOC-NONEXISTENT", store=empty_store) == []


def test_12_invalid_query(populated_store: VectorStore):
    """12. Verify empty, whitespace-only, or non-string queries raise `ValueError`."""
    for bad_query in ("", "   \n\t  ", None, 12345, ["list_query"]):
        with pytest.raises(ValueError):
            retrieve_relevant_chunks(bad_query, store=populated_store)  # type: ignore[arg-type]


def test_13_invalid_filters(populated_store: VectorStore):
    """13. Verify invalid `top_k`, `min_relevance`, `file_type`, or operator-injected filters raise `ValueError`."""
    with pytest.raises(ValueError):
        retrieve_relevant_chunks("valid query", top_k=0, store=populated_store)

    with pytest.raises(ValueError):
        retrieve_relevant_chunks("valid query", min_relevance=1.5, store=populated_store)

    with pytest.raises(ValueError):
        retrieve_relevant_chunks("valid query", min_relevance=-0.1, store=populated_store)

    with pytest.raises(ValueError, match="Unsupported file_type"):
        retrieve_relevant_chunks("valid query", file_type="exe", store=populated_store)

    with pytest.raises(ValueError):
        retrieve_relevant_chunks("valid query", category="", store=populated_store)

    with pytest.raises(ValueError):
        retrieve_relevant_chunks("valid query", document_id="$ne", store=populated_store)


def test_14_missing_metadata_handled_safely():
    """
    14. Verify chunks with sparse/missing metadata fields are normalized with safe defaults
    and missing distance values do not crash ranking.
    """
    mock_store = MagicMock(spec=VectorStore)
    mock_store.collection_name = "jeevan_setu_knowledge"
    mock_col = MagicMock()
    mock_col.count.return_value = 1
    mock_col.metadata = {"hnsw:space": "cosine"}
    mock_col.query.return_value = {
        "ids": [["sparse_chunk_1"]],
        "documents": [["Minimal protocol guidance text with sparse metadata."]],
        "metadatas": [[{}]],
        "distances": [[None]],
    }
    mock_store.get_or_create_collection.return_value = mock_col

    hits = retrieve_relevant_chunks(
        query="minimal protocol guidance",
        store=mock_store,
        min_relevance=0.0,
    )
    assert len(hits) == 1
    hit = hits[0]
    assert hit["chunk_id"] == "sparse_chunk_1"
    assert hit["source"] == "unknown"
    assert hit["category"] == "general"
    assert hit["page_number"] is None
    assert hit["distance"] is None
    assert hit["relevance_score"] == 0.0


def test_15_source_and_page_traceability(populated_store: VectorStore):
    """
    15. Verify PDF chunks retain exact 1-based `page_number`, DOCX chunks keep `page_number=None`
    (never fabricated), and `extract_source_references` formats structured citations.
    """
    hits = retrieve_relevant_chunks(
        query="NEWS2 scoring and ICU to HDU step-down transfer",
        top_k=4,
        min_relevance=0.0,
        store=populated_store,
    )
    refs = extract_source_references(hits)
    assert len(refs) == len(hits)

    by_doc = {r["document_id"]: r for r in refs}
    news2_ref = by_doc["DOC-NEWS2-001"]
    assert news2_ref["page_number"] == 3
    assert news2_ref["citation"] == "approved_guidelines/news2_clinical_scoring.pdf (p. 3)"

    hdu_docx_ref = by_doc["DOC-HDU-SOP-002"]
    assert hdu_docx_ref["page_number"] is None
    assert hdu_docx_ref["citation"] == "hospital_sops/icu_to_hdu_stepdown.docx"


def test_16_image_reference_preservation(populated_store: VectorStore):
    """16. Verify retrieved chunks preserve `image_assets` references for multimodal workflows."""
    hits = retrieve_relevant_chunks(
        query="NEWS2 clinical scoring threshold 7",
        document_id="DOC-NEWS2-001",
        top_k=1,
        store=populated_store,
    )
    assert len(hits) == 1
    assets = hits[0]["image_assets"]
    assert len(assets) == 1
    assert assets[0]["image_id"] == "img_news2_chart_p3"
    assert assets[0]["asset_path"] == "_extracted_assets/news2_chart_p3.png"
    assert assets[0]["page_number"] == 3


def test_17_patient_data_isolation():
    """
    17. Verify the retriever blocks patient-named collections, rejects UHID filters,
    and filters out any chunk record contaminated with `UHID-YYYY-NNNNN` or `patient_id`.
    """
    # 1. Reject VectorStore pointing to a patient collection
    bad_store = MagicMock(spec=VectorStore)
    bad_store.collection_name = "patient_medical_records"
    with pytest.raises(ValueError, match="restricted to the shared knowledge collection"):
        retrieve_relevant_chunks("query", store=bad_store)

    # 2. Reject UHID in filter parameter
    with pytest.raises(ValueError, match="UHID"):
        retrieve_relevant_chunks("query", document_id="UHID-2026-00001")

    # 3. Filter out any contaminated record returned by underlying store
    contaminated_store = MagicMock(spec=VectorStore)
    contaminated_store.collection_name = "jeevan_setu_knowledge"
    mock_col = MagicMock()
    mock_col.count.return_value = 2
    mock_col.metadata = {"hnsw:space": "cosine"}
    mock_col.query.return_value = {
        "ids": [["leaked_phi_chunk", "clean_protocol_chunk"]],
        "documents": [[
            "Patient record UHID-2026-00002 has elevated heart rate.",
            "Standard protocol for arterial line zeroing and transducer leveling.",
        ]],
        "metadatas": [
            [
                {"source": "leak.txt", "category": "general"},
                {"source": "clinical_protocols/art_line.md", "category": "clinical_protocols", "document_id": "DOC-ART-1"},
            ]
        ],
        "distances": [[0.10, 0.20]],
    }
    contaminated_store.get_or_create_collection.return_value = mock_col

    hits = retrieve_relevant_chunks("arterial line protocol", store=contaminated_store, min_relevance=0.0)
    assert len(hits) == 1
    assert hits[0]["chunk_id"] == "clean_protocol_chunk"


def test_18_chromadb_error_handling():
    """18. Verify unavailable or failing ChromaDB operations are caught safely and return `[]`."""
    broken_store = MagicMock(spec=VectorStore)
    broken_store.collection_name = "jeevan_setu_knowledge"
    broken_store.get_or_create_collection.side_effect = RuntimeError("Simulated ChromaDB disk I/O failure")

    results = retrieve_relevant_chunks("sepsis bundle guidelines", store=broken_store)
    assert results == []

    doc_results = retrieve_by_document_id("DOC-ANY", store=broken_store)
    assert doc_results == []
