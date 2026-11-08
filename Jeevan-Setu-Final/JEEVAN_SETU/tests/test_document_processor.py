"""
tests/test_document_processor.py — Comprehensive pytest suite for Jeevan Setu RAG `document_processor.py`.

Covers all 18 required test scenarios using synthetic non-patient content only:
1. Whitespace cleaning.
2. Paragraph preservation.
3. Heading preservation.
4. List preservation.
5. Clinical values and units remain unchanged.
6. Table text preservation.
7. Configurable chunk size.
8. Configurable overlap.
9. Short documents.
10. Oversized paragraphs.
11. Empty and invalid documents.
12. No missing text between chunks.
13. No unnecessary duplicate chunks.
14. Stable chunk IDs across repeated runs.
15. PDF page metadata preservation.
16. DOCX source metadata preservation (without inventing page numbers).
17. Image asset reference preservation (without raw bytes/base64 or patient-specific images).
18. Compatibility with the existing embedding and vector store interfaces (using `tmp_path`).
"""

import copy
from pathlib import Path
from typing import Dict, Any, List

import pytest

from chatbot.rag.document_processor import (
    DEFAULT_CHUNK_OVERLAP_TOKENS,
    DEFAULT_CHUNK_SIZE_TOKENS,
    clean_document_content,
    clean_text,
    chunk_text,
    estimate_token_count,
    process_document,
    process_documents,
)
from chatbot.rag.embedding_service import get_embedding, get_embeddings
from chatbot.rag.vector_store import VectorStore, validate_metadata


def test_01_whitespace_cleaning():
    """1. Verify normalization of line endings, non-breaking spaces, zero-width chars, and repeated blank lines."""
    raw = (
        "  First   line\u00a0with\u200b   irregular\t\tspaces.  \r\n"
        "\r\n"
        "\r\n"
        "\r\n"
        "Second line with cardiorespi-\n"
        "ratory monitoring.   \r"
    )
    cleaned = clean_text(raw)
    assert "\r" not in cleaned
    assert "\u00a0" not in cleaned
    assert "\u200b" not in cleaned
    assert "\n\n\n" not in cleaned
    assert cleaned == (
        "First line with irregular spaces.\n\n"
        "Second line with cardiorespiratory monitoring."
    )


def test_02_paragraph_preservation():
    """2. Verify meaningful paragraph boundaries (`\\n\\n`) are preserved during cleaning and chunking."""
    raw = (
        "Paragraph one describes standard admission criteria for high-dependency units.\n\n\n\n"
        "Paragraph two describes continuous pulse oximetry and noninvasive arterial pressure checks.\n\n"
        "Paragraph three describes step-down discharge readiness criteria."
    )
    cleaned = clean_text(raw)
    paragraphs = cleaned.split("\n\n")
    assert len(paragraphs) == 3
    assert paragraphs[0].startswith("Paragraph one")
    assert paragraphs[1].startswith("Paragraph two")
    assert paragraphs[2].startswith("Paragraph three")


def test_03_heading_preservation():
    """3. Verify Markdown and uppercase clinical section headings are preserved and kept attached to their section."""
    raw = (
        "# SECTION 1: ICU STEP-DOWN CRITERIA\n\n"
        "Patients must demonstrate hemodynamic stability for at least 12 consecutive hours.\n\n"
        "## 1.1 Respiratory Thresholds\n\n"
        "Spontaneous breathing or stable noninvasive support with FiO2 <= 40%."
    )
    cleaned = clean_text(raw)
    assert "# SECTION 1: ICU STEP-DOWN CRITERIA" in cleaned
    assert "## 1.1 Respiratory Thresholds" in cleaned

    chunks = chunk_text(cleaned, chunk_size=30, overlap=5)
    assert len(chunks) >= 2
    # Heading should stay attached to its paragraph rather than stranded alone
    assert "# SECTION 1: ICU STEP-DOWN CRITERIA" in chunks[0]
    assert "hemodynamic stability" in chunks[0]


def test_04_list_preservation():
    """4. Verify numbered lists, lettered lists, and bullet points (including nested indentation) are preserved."""
    raw = (
        " Standard Pre-Transfer Checklist:\n"
        "1. Verify airway patency and oxygen reserve.\n"
        "2. Confirm infusion pump battery >= 80%.\n"
        "   - Norepinephrine concentration labeled.\n"
        "   - Normal saline flush line connected.\n"
        "• Document handover timestamp in ward register."
    )
    cleaned = clean_text(raw)
    lines = cleaned.split("\n")
    assert lines[1] == "1. Verify airway patency and oxygen reserve."
    assert lines[2] == "2. Confirm infusion pump battery >= 80%."
    assert lines[3] == "  - Norepinephrine concentration labeled."
    assert lines[4] == "  - Normal saline flush line connected."
    assert lines[5] == "• Document handover timestamp in ward register."


def test_05_clinical_values_and_units_remain_unchanged():
    """5. Verify exact clinical terminology, numerical values, ranges, comparators, and units remain untouched."""
    clinical_text = (
        "Target MAP >= 65 mmHg; SpO2 94-98% (or 88-92% in chronic hypercapnia); "
        "Arterial pH 7.35-7.45; PaCO2 35-45 mmHg; Lactate < 2.0 mmol/L; "
        "Temperature 36.5-37.5 °C; Heparin infusion 12 units/kg/hr; "
        "Potassium 4.0 ± 0.5 mEq/L; Troponin-I <= 0.04 ng/mL."
    )
    cleaned = clean_text(clinical_text)
    assert cleaned == clinical_text

    chunks = chunk_text(clinical_text, chunk_size=800, overlap=120)
    assert len(chunks) == 1
    assert chunks[0] == clinical_text


def test_06_table_text_preservation():
    """6. Verify pipe-delimited tables from DOCX/Markdown are preserved in readable form."""
    raw_table = (
        "| Parameter   | Normal Range   | High-Risk Threshold |\n"
        "|  Heart Rate | 60-90 bpm      | > 130 bpm           |\n"
        "|  SpO2       | >= 96%         | <= 91%              |\n"
        "|  Systolic BP| 110-140 mmHg   | <= 90 mmHg          |"
    )
    cleaned = clean_text(raw_table)
    expected_lines = [
        "| Parameter | Normal Range | High-Risk Threshold |",
        "| Heart Rate | 60-90 bpm | > 130 bpm |",
        "| SpO2 | >= 96% | <= 91% |",
        "| Systolic BP | 110-140 mmHg | <= 90 mmHg |",
    ]
    assert cleaned.split("\n") == expected_lines


def test_07_configurable_chunk_size():
    """7. Verify default chunk configuration (800 / 120) and custom configurable `chunk_size`."""
    assert DEFAULT_CHUNK_SIZE_TOKENS == 800
    assert DEFAULT_CHUNK_OVERLAP_TOKENS == 120

    paragraphs = [
        f"Section {i}: Continuous telemetry monitoring requires checking respiratory rate, "
        f"oxygen saturation, blood pressure, and consciousness score every 15 minutes during stabilization."
        for i in range(1, 15)
    ]
    long_text = "\n\n".join(paragraphs)

    small_chunks = chunk_text(long_text, chunk_size=60, overlap=10)
    large_chunks = chunk_text(long_text, chunk_size=180, overlap=20)

    assert len(small_chunks) > len(large_chunks) >= 2
    for ch in small_chunks:
        assert estimate_token_count(ch) <= 65


def test_08_configurable_overlap():
    """8. Verify configurable `overlap` preserves overlapping context between consecutive chunks."""
    sentences = [
        f"Observation {i}: The bedside monitor recorded stable sinus rhythm with normal QRS duration."
        for i in range(1, 12)
    ]
    text = "\n\n".join(sentences)

    no_overlap_chunks = chunk_text(text, chunk_size=50, overlap=0)
    with_overlap_chunks = chunk_text(text, chunk_size=50, overlap=20)

    assert len(no_overlap_chunks) >= 3
    assert len(with_overlap_chunks) >= len(no_overlap_chunks)

    # Consecutive chunks with overlap > 0 must share overlapping text from the tail of chunk[0]
    tail_line_of_first = with_overlap_chunks[0].split("\n\n")[-1]
    assert tail_line_of_first in with_overlap_chunks[1]

    # Invalid overlap >= chunk_size must raise ValueError
    with pytest.raises(ValueError):
        chunk_text(text, chunk_size=50, overlap=50)


def test_09_short_documents():
    """9. Verify short documents produce exactly one chunk without unnecessary fragmentation."""
    short_doc = {
        "document_id": "doc_short_sop_001",
        "source": "hospital_sops/handover_note.md",
        "category": "hospital_sops",
        "file_type": "markdown",
        "content": "Brief SOP: Verify verbal and written SBAR handover before bed transfer.",
    }
    chunks = process_document(short_doc)
    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["total_chunks"] == 1
    assert chunks[0]["content"] == short_doc["content"]


def test_10_oversized_paragraphs():
    """10. Verify a single massive paragraph with no paragraph breaks is safely split without losing clinical label-value pairs."""
    # Construct a single paragraph > 250 tokens with clinical Label: Value pairs
    clauses = [
        f"Checkpoint {i} records Heart_Rate: {70 + (i % 20)} bpm and SpO2: {95 + (i % 4)} % under standard protocol."
        for i in range(1, 30)
    ]
    huge_paragraph = " ".join(clauses)
    assert "\n" not in huge_paragraph
    assert estimate_token_count(huge_paragraph) > 300

    chunks = chunk_text(huge_paragraph, chunk_size=90, overlap=15)
    assert len(chunks) >= 4
    for i in range(1, 30):
        marker = f"Checkpoint {i} records Heart_Rate: {70 + (i % 20)} bpm"
        assert any(marker in c for c in chunks), f"Missing or split label-value pair: {marker}"


def test_11_empty_and_invalid_documents():
    """11. Verify empty strings, whitespace-only records, non-dict records, and patient UHID records are handled safely."""
    assert clean_text("") == ""
    assert clean_text("   \n\t\r\n  ") == ""
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []

    invalid_inputs: List[Any] = [
        None,
        "not_a_dict",
        12345,
        {},
        {"source": "empty.txt", "content": ""},
        {"source": "whitespace.txt", "content": "   \n\t  "},
        {"source": "bad_content.txt", "content": None},
        # Patient UHID guardrail test (must never enter shared RAG chunks)
        {"source": "clinical_note.txt", "content": "Patient record UHID-2026-00001 vitals summary."},
        # Patient-specific field guardrail test
        {"source": "patient_img.txt", "patient_id": 1, "content": "Patient bedside chart."},
    ]
    for bad_doc in invalid_inputs:
        assert process_document(bad_doc) == []

    assert process_documents(invalid_inputs) == []
    assert process_documents([]) == []


def test_12_no_missing_text_between_chunks():
    """12. Verify every single sentence/item from a multi-section document is present in the output chunks in order."""
    distinct_items = [
        f"UNIQUE_PROTOCOL_STATEMENT_{idx:03d}: Maintain mean arterial pressure above 65 mmHg during transport."
        for idx in range(1, 45)
    ]
    full_text = "\n\n".join(distinct_items)

    chunks = chunk_text(full_text, chunk_size=100, overlap=20)
    assert len(chunks) >= 5

    # Every unique statement must appear in at least one chunk, and first appearance order must be monotonic
    first_seen_chunk_indices: List[int] = []
    for idx in range(1, 45):
        token = f"UNIQUE_PROTOCOL_STATEMENT_{idx:03d}"
        matching_chunk_idxs = [c_i for c_i, c_text in enumerate(chunks) if token in c_text]
        assert matching_chunk_idxs, f"Statement {token} was lost between chunks!"
        first_seen_chunk_indices.append(matching_chunk_idxs[0])

    assert first_seen_chunk_indices == sorted(first_seen_chunk_indices)


def test_13_no_unnecessary_duplicate_chunks():
    """13. Verify repeated or duplicate document records do not produce duplicate chunks, and original input is not mutated."""
    doc = {
        "document_id": "doc_dup_check_001",
        "source": "approved_guidelines/oxygen_titration.md",
        "category": "approved_guidelines",
        "file_type": "markdown",
        "page_number": None,
        "ocr_required": False,
        "image_assets": [],
        "content": " Paragraph A: Titrate oxygen to target SpO2 94-98%.\n\n\nParagraph B: Reassess ABG in 30 minutes. ",
    }
    original_snapshot = copy.deepcopy(doc)

    # Pass duplicate document records in the batch
    chunks = process_documents([doc, copy.deepcopy(doc)])
    assert len(chunks) == 1
    assert doc == original_snapshot, "process_documents must not mutate input document records"

    cleaned_copy = clean_document_content(doc)
    assert doc == original_snapshot, "clean_document_content must not mutate input dict"
    assert cleaned_copy["content"].startswith("Paragraph A:")


def test_14_stable_chunk_ids_across_repeated_runs():
    """14. Verify deterministic `chunk_id` and `content_hash` generation across repeated runs."""
    doc = {
        "document_id": "doc_ventilator_sop_abc123",
        "source": "clinical_protocols/ventilator_weaning.pdf",
        "category": "clinical_protocols",
        "file_type": "pdf",
        "page_number": 3,
        "content": "\n\n".join(
            [f"Step {i}: Evaluate spontaneous breathing trial tolerance over 30 minutes." for i in range(1, 20)]
        ),
    }

    run_1 = process_document(doc, chunk_size=80, overlap=15)
    run_2 = process_document(doc, chunk_size=80, overlap=15)

    assert len(run_1) >= 2
    assert [c["chunk_id"] for c in run_1] == [c["chunk_id"] for c in run_2]
    assert [c["content_hash"] for c in run_1] == [c["content_hash"] for c in run_2]
    assert len({c["chunk_id"] for c in run_1}) == len(run_1)


def test_15_pdf_page_metadata_preservation():
    """15. Verify PDF page-level records retain 1-based `page_number`, `file_type='pdf'`, and `ocr_required`."""
    pdf_page_records = [
        {
            "document_id": "doc_icu_manual_p1_111111",
            "source": "clinical_protocols/icu_manual.pdf",
            "category": "clinical_protocols",
            "file_type": "pdf",
            "page_number": 1,
            "ocr_required": False,
            "image_assets": [],
            "content": "Page 1: Triage scoring and admission workflow for critical care units.",
        },
        {
            "document_id": "doc_icu_manual_p2_222222",
            "source": "clinical_protocols/icu_manual.pdf",
            "category": "clinical_protocols",
            "file_type": "pdf",
            "page_number": 2,
            "ocr_required": True,
            "image_assets": [],
            "content": "[Scanned or image-only PDF page 2 in clinical_protocols/icu_manual.pdf; no machine-readable text layer found — OCR or vision processing required.]",
        },
    ]

    chunks = process_documents(pdf_page_records)
    assert len(chunks) == 2

    assert chunks[0]["page_number"] == 1
    assert chunks[0]["file_type"] == "pdf"
    assert chunks[0]["ocr_required"] is False
    assert chunks[0]["metadata"]["page_number"] == 1

    assert chunks[1]["page_number"] == 2
    assert chunks[1]["file_type"] == "pdf"
    assert chunks[1]["ocr_required"] is True
    assert chunks[1]["metadata"]["page_number"] == 2
    assert chunks[0]["chunk_id"] != chunks[1]["chunk_id"]


def test_16_docx_source_metadata_preservation():
    """16. Verify DOCX records retain source traceability and `file_type='docx'` without inventing page numbers."""
    docx_record = {
        "document_id": "doc_transfer_sop_998877",
        "source": "hospital_sops/icu_to_hdu_transfer.docx",
        "category": "hospital_sops",
        "file_type": "docx",
        "page_number": 99,  # Even if an invalid page number were passed on a DOCX, processor must not invent/keep it
        "ocr_required": False,
        "image_assets": [],
        "content": "Standard Operating Procedure for ICU to HDU patient handover and bed allocation.",
    }

    chunks = process_document(docx_record)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["source"] == "hospital_sops/icu_to_hdu_transfer.docx"
    assert chunk["category"] == "hospital_sops"
    assert chunk["file_type"] == "docx"
    assert chunk["page_number"] is None
    assert "page_number" not in chunk["metadata"]


def test_17_image_asset_reference_preservation():
    """
    17. Verify multimodal readiness: extracted image asset references are preserved with source/page metadata,
    while raw bytes, base64 data URIs, and patient-specific image assets are stripped/blocked.
    """
    doc_with_images = {
        "document_id": "doc_triage_flowchart_p1_abcdef",
        "source": "clinical_protocols/triage_flowchart.pdf",
        "category": "clinical_protocols",
        "file_type": "pdf",
        "page_number": 1,
        "ocr_required": False,
        "content": "Triage decision tree for step-up and step-down transfers. data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA",
        "image_assets": [
            {
                "image_id": "img_triage_flowchart_p1_1_a1b2c3d4e5",
                "source_document": "clinical_protocols/triage_flowchart.pdf",
                "document_id": "doc_triage_flowchart_p1_abcdef",
                "page_number": 1,
                "image_format": "png",
                "file_size": 4096,
                "asset_path": "_extracted_assets/triage_flowchart_p1_img1_a1b2c3d4e5.png",
                "raw_bytes": b"\x89PNG\r\n",  # Must be stripped from chunk image_assets
            },
            # Patient-specific image asset (must be rejected)
            {
                "image_id": "img_patient_xray_01",
                "patient_id": 4,
                "asset_path": "secure_uploads/p4_xray.png",
            },
            # Base64 URI in asset_path (must be rejected)
            {
                "image_id": "img_base64_bad",
                "asset_path": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==",
            },
        ],
    }

    chunks = process_document(doc_with_images)
    assert len(chunks) == 1
    ch = chunks[0]

    # Base64 URI in text content must be replaced with a clean placeholder
    assert "data:image/png;base64" not in ch["content"]
    assert len(ch["image_assets"]) == 1

    asset = ch["image_assets"][0]
    assert asset["image_id"] == "img_triage_flowchart_p1_1_a1b2c3d4e5"
    assert asset["document_id"] == "doc_triage_flowchart_p1_abcdef"
    assert asset["source_document"] == "clinical_protocols/triage_flowchart.pdf"
    assert asset["page_number"] == 1
    assert asset["asset_path"] == "_extracted_assets/triage_flowchart_p1_img1_a1b2c3d4e5.png"
    assert "raw_bytes" not in asset

    # ChromaDB scalar metadata reflects image presence without embedding lists/dicts
    assert ch["metadata"]["has_images"] is True
    assert ch["metadata"]["image_count"] == 1
    assert ch["metadata"]["image_ids"] == "img_triage_flowchart_p1_1_a1b2c3d4e5"


def test_18_compatibility_with_embedding_service_and_vector_store(tmp_path: Path):
    """
    18. Verify processed chunks work directly with `embedding_service.py` and `vector_store.py`
    using an isolated temporary directory (`tmp_path`).
    """
    sample_docs: List[Dict[str, Any]] = [
        {
            "document_id": "doc_news2_guide_p1_101010",
            "source": "approved_guidelines/news2_scoring.pdf",
            "category": "approved_guidelines",
            "file_type": "pdf",
            "page_number": 1,
            "ocr_required": False,
            "image_assets": [
                {
                    "image_id": "img_news2_chart_p1_1",
                    "source_document": "approved_guidelines/news2_scoring.pdf",
                    "document_id": "doc_news2_guide_p1_101010",
                    "page_number": 1,
                    "image_format": "png",
                    "file_size": 2048,
                    "asset_path": "_extracted_assets/news2_chart_p1_1.png",
                }
            ],
            "content": (
                "# NEWS2 National Early Warning Score Thresholds\n\n"
                "A total NEWS2 score of 7 or more represents a high clinical risk threshold "
                "requiring urgent critical care assessment and continuous bedside telemetry."
            ),
        },
        {
            "document_id": "doc_hdu_admission_sop_202020",
            "source": "hospital_sops/hdu_stepdown_sop.docx",
            "category": "hospital_sops",
            "file_type": "docx",
            "page_number": None,
            "ocr_required": False,
            "image_assets": [],
            "content": (
                "High Dependency Unit (HDU) step-down admission requires stable airway protection, "
                "vasopressor weaning completion, and documented nursing handover."
            ),
        },
    ]

    chunks = process_documents(sample_docs, chunk_size=800, overlap=120)
    assert len(chunks) == 2

    # Required top-level fields on every chunk
    required_keys = {
        "chunk_id",
        "document_id",
        "source",
        "category",
        "file_type",
        "page_number",
        "chunk_index",
        "total_chunks",
        "content",
        "content_hash",
        "image_assets",
    }
    for ch in chunks:
        assert required_keys.issubset(ch.keys())
        # Verify ChromaDB metadata validator accepts `ch["metadata"]`
        validated_meta = validate_metadata(ch["metadata"])
        assert validated_meta["chunk_id"] == ch["chunk_id"]
        assert validated_meta["document_id"] == ch["document_id"]

    # Verify batch embedding generation works on chunk contents
    embeddings = get_embeddings([c["content"] for c in chunks])
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 384

    # Verify VectorStore.add_chunks() and semantic search in isolated tmp_path
    store = VectorStore(storage_dir=tmp_path / "isolated_chroma", collection_name="test_processor_compat")
    stored_ids = store.add_chunks(chunks)
    assert stored_ids == [c["chunk_id"] for c in chunks]
    assert store.get_collection_count() == 2

    results = store.search("What NEWS2 score indicates high clinical risk?", top_k=1)
    assert len(results) == 1
    assert results[0]["id"] == chunks[0]["chunk_id"]
    assert results[0]["metadata"]["page_number"] == 1
    assert results[0]["metadata"]["file_type"] == "pdf"

