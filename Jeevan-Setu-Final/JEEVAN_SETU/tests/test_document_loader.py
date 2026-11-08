"""
tests/test_document_loader.py — Comprehensive Pytest Suite for Jeevan Setu RAG Document Loader.

Uses synthetic fixtures in `tmp_path` only; never reads, modifies, or deletes
the production `JEEVAN_SETU/knowledge_base/` or `JEEVAN_SETU/vector_storage/`.
"""

import io
import json
import sys
import zlib
from pathlib import Path

import docx
import pypdf
import pytest
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from chatbot.rag.document_loader import (
    KNOWLEDGE_BASE_DIR,
    get_knowledge_base_assets_dir,
    get_knowledge_base_dir,
    load_documents,
)
from chatbot.rag.document_processor import process_documents


# ---------------------------------------------------------------------------
# Synthetic binary helpers (no clinical/patient data)
# ---------------------------------------------------------------------------

VALID_1X1_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

VALID_1X1_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c"
    b"\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c"
    b"(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00"
    b"?\x00\xfb\xd2\x8a(\x03\xff\xd9"
)


def _create_synthetic_pdf_with_text_and_images(
    target_path: Path,
    pages_text: list[str],
    page_images: dict[int, list[bytes]] = None,
) -> None:
    """
    Build a valid synthetic PDF using pypdf with optional text per page and
    optional embedded DCTDecode/PNG image XObjects per 1-based page number.
    """
    writer = pypdf.PdfWriter()
    page_images = page_images or {}

    # Shared Helvetica font resource for text rendering
    font_dict = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font_dict)

    for idx, text in enumerate(pages_text):
        page_num = idx + 1
        page = writer.add_blank_page(width=400, height=400)
        resources = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
        })

        # Add text content stream if non-empty
        if text:
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_bytes = f"BT /F1 12 Tf 36 350 Td ({escaped}) Tj ET".encode("latin-1")
            content_stream = DecodedStreamObject()
            content_stream.set_data(stream_bytes)
            page[NameObject("/Contents")] = writer._add_object(content_stream)

        # Attach any requested image XObjects for this page
        imgs_for_page = page_images.get(page_num, [])
        if imgs_for_page:
            xobj_dict = DictionaryObject()
            for img_idx, img_bytes in enumerate(imgs_for_page):
                img_stream = DecodedStreamObject()
                img_stream.set_data(img_bytes)
                img_stream.update({
                    NameObject("/Type"): NameObject("/XObject"),
                    NameObject("/Subtype"): NameObject("/Image"),
                    NameObject("/Width"): NumberObject(1),
                    NameObject("/Height"): NumberObject(1),
                    NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                    NameObject("/BitsPerComponent"): NumberObject(8),
                    NameObject("/Filter"): NameObject("/DCTDecode"),
                })
                xobj_dict[NameObject(f"/Im{img_idx}")] = writer._add_object(img_stream)
            resources[NameObject("/XObject")] = xobj_dict

        page[NameObject("/Resources")] = resources

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "wb") as fh:
        writer.write(fh)


# ---------------------------------------------------------------------------
# Tests (1 - 14)
# ---------------------------------------------------------------------------

def test_01_knowledge_base_directory_resolution(tmp_path: Path):
    """1. Verify canonical knowledge-base and extracted-assets directory resolution."""
    kb_dir = get_knowledge_base_dir()
    assert kb_dir == BACKEND_ROOT / "knowledge_base"
    assert kb_dir == KNOWLEDGE_BASE_DIR

    assets_dir = get_knowledge_base_assets_dir(tmp_path)
    assert assets_dir == tmp_path.resolve() / "_extracted_assets"


def test_02_missing_directory_returns_empty_list(tmp_path: Path):
    """2. Verify missing or non-existent directory returns an empty list safely."""
    missing = tmp_path / "non_existent_kb"
    docs = load_documents(base_dir=missing)
    assert docs == []


def test_03_txt_and_markdown_extraction(tmp_path: Path):
    """3. Verify TXT, .md, and .markdown extraction with UTF-8 content and categories."""
    sop_dir = tmp_path / "hospital_sops"
    sop_dir.mkdir()

    (sop_dir / "shift_handover.txt").write_text(
        "Standard shift handover checklist for engineering equipment.",
        encoding="utf-8",
    )
    (sop_dir / "alarm_guide.md").write_text(
        "# Acoustic Alarm Tiers\n\nTier 1 indicates high-priority acoustic alert.",
        encoding="utf-8",
    )
    (tmp_path / "root_note.markdown").write_text(
        "Root level markdown reference note.",
        encoding="utf-8",
    )

    docs = load_documents(base_dir=tmp_path)
    assert len(docs) == 3

    by_source = {d["source"].replace("\\", "/"): d for d in docs}
    assert by_source["hospital_sops/shift_handover.txt"]["file_type"] == "txt"
    assert by_source["hospital_sops/shift_handover.txt"]["category"] == "hospital_sops"
    assert "shift handover checklist" in by_source["hospital_sops/shift_handover.txt"]["content"]

    assert by_source["hospital_sops/alarm_guide.md"]["file_type"] == "markdown"
    assert by_source["root_note.markdown"]["file_type"] == "markdown"
    assert by_source["root_note.markdown"]["category"] == "general"


def test_04_json_extraction_and_malformed_json_handling(tmp_path: Path):
    """4. Verify valid JSON is converted to readable text and malformed JSON is skipped safely."""
    proto_dir = tmp_path / "clinical_protocols"
    proto_dir.mkdir()

    valid_payload = {
        "protocol_title": "Facility Power Backup Procedure",
        "steps": ["Verify generator fuel level", "Engage automatic transfer switch"],
        "version": 2,
    }
    (proto_dir / "power_backup.json").write_text(json.dumps(valid_payload), encoding="utf-8")
    (proto_dir / "broken.json").write_text("{malformed_json: [1, 2,", encoding="utf-8")

    docs = load_documents(base_dir=tmp_path)
    assert len(docs) == 1
    doc = docs[0]
    assert doc["file_type"] == "json"
    assert doc["category"] == "clinical_protocols"
    assert "Facility Power Backup Procedure" in doc["content"]
    assert "Engage automatic transfer switch" in doc["content"]


def test_05_pdf_page_by_page_extraction_and_page_numbers(tmp_path: Path):
    """5. Verify PDF page-by-page extraction, 1-based page numbers, and scanned page OCR notice."""
    pdf_path = tmp_path / "project_documentation" / "architecture_manual.pdf"
    _create_synthetic_pdf_with_text_and_images(
        pdf_path,
        pages_text=[
            "Page One: Telemetry Gateway Architecture Overview.",
            "Page Two: Message Queue Routing Specification.",
            "",  # Blank/scanned page 3 with no text layer
        ],
    )

    docs = load_documents(base_dir=tmp_path)
    assert len(docs) == 3

    assert docs[0]["page_number"] == 1
    assert docs[0]["file_type"] == "pdf"
    assert docs[0]["ocr_required"] is False
    assert "Page One: Telemetry Gateway Architecture Overview." in docs[0]["content"]

    assert docs[1]["page_number"] == 2
    assert docs[1]["ocr_required"] is False
    assert "Page Two: Message Queue Routing Specification." in docs[1]["content"]

    assert docs[2]["page_number"] == 3
    assert docs[2]["ocr_required"] is True
    assert "OCR or vision processing required" in docs[2]["content"]


def test_06_docx_paragraph_and_table_extraction(tmp_path: Path):
    """6. Verify DOCX extracts paragraphs and tables in readable order."""
    docx_path = tmp_path / "approved_guidelines" / "equipment_calibration.docx"
    docx_path.parent.mkdir(parents=True, exist_ok=True)

    doc = docx.Document()
    doc.add_paragraph("Introduction: Sensor Calibration Schedule.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Sensor Type"
    table.cell(0, 1).text = "Interval"
    table.cell(1, 0).text = "Optical Probe"
    table.cell(1, 1).text = "Every 30 Days"
    doc.add_paragraph("Conclusion: Log all calibration results.")
    doc.save(str(docx_path))

    docs = load_documents(base_dir=tmp_path)
    assert len(docs) == 1
    record = docs[0]
    assert record["file_type"] == "docx"
    assert record["page_number"] is None
    content = record["content"]

    intro_pos = content.find("Introduction: Sensor Calibration Schedule.")
    table_pos = content.find("| Optical Probe | Every 30 Days |")
    concl_pos = content.find("Conclusion: Log all calibration results.")
    assert intro_pos != -1 and table_pos != -1 and concl_pos != -1
    assert intro_pos < table_pos < concl_pos


def test_07_pdf_embedded_image_extraction_and_metadata(tmp_path: Path):
    """7. Verify PDF embedded images are extracted to asset directory with source and page metadata."""
    pdf_path = tmp_path / "clinical_protocols" / "waveform_guide.pdf"
    _create_synthetic_pdf_with_text_and_images(
        pdf_path,
        pages_text=["Waveform reference diagram page."],
        page_images={1: [VALID_1X1_JPEG]},
    )

    docs = load_documents(base_dir=tmp_path)
    assert len(docs) == 1
    rec = docs[0]
    assert len(rec["image_assets"]) == 1

    img_meta = rec["image_assets"][0]
    assert img_meta["source_document"] == "clinical_protocols/waveform_guide.pdf"
    assert img_meta["document_id"] == rec["document_id"]
    assert img_meta["page_number"] == 1
    assert img_meta["image_format"] == "jpg"
    assert img_meta["file_size"] == len(VALID_1X1_JPEG)
    assert img_meta["asset_path"].startswith("_extracted_assets/")

    saved_file = tmp_path / img_meta["asset_path"]
    assert saved_file.is_file()
    assert saved_file.read_bytes() == VALID_1X1_JPEG
    # Ensure no base64 or raw image bytes are placed in text content
    assert "JFIF" not in rec["content"]


def test_08_docx_embedded_image_extraction_and_metadata(tmp_path: Path):
    """8. Verify DOCX embedded images are extracted with source metadata and page_number=None."""
    docx_path = tmp_path / "hospital_sops" / "layout_diagram.docx"
    docx_path.parent.mkdir(parents=True, exist_ok=True)

    doc = docx.Document()
    doc.add_paragraph("Floor layout diagram below:")
    doc.add_picture(io.BytesIO(VALID_1X1_PNG))
    doc.save(str(docx_path))

    docs = load_documents(base_dir=tmp_path)
    assert len(docs) == 1
    rec = docs[0]
    assert len(rec["image_assets"]) == 1

    img_meta = rec["image_assets"][0]
    assert img_meta["source_document"] == "hospital_sops/layout_diagram.docx"
    assert img_meta["document_id"] == rec["document_id"]
    assert img_meta["page_number"] is None
    assert img_meta["image_format"] == "png"
    assert img_meta["file_size"] == len(VALID_1X1_PNG)

    saved_file = tmp_path / img_meta["asset_path"]
    assert saved_file.is_file()
    assert saved_file.read_bytes() == VALID_1X1_PNG


def test_09_corrupt_pdf_docx_and_image_handling(tmp_path: Path):
    """9. Verify corrupt PDF, corrupt DOCX, and corrupt embedded images are skipped gracefully."""
    (tmp_path / "corrupt.pdf").write_bytes(b"%PDF-1.4 broken binary garbage")
    (tmp_path / "corrupt.docx").write_bytes(b"PK\x03\x04 corrupt zip stream")

    # PDF with one corrupt image stream and one valid image stream
    pdf_with_bad_img = tmp_path / "mixed_images.pdf"
    _create_synthetic_pdf_with_text_and_images(
        pdf_with_bad_img,
        pages_text=["Page with one corrupt image and one valid image."],
        page_images={1: [b"not_an_image_at_all", VALID_1X1_JPEG]},
    )

    docs = load_documents(base_dir=tmp_path)
    assert len(docs) == 1
    assert docs[0]["source"] == "mixed_images.pdf"
    assert len(docs[0]["image_assets"]) == 1
    assert docs[0]["image_assets"][0]["image_format"] == "jpg"


def test_10_unsupported_and_hidden_files_ignored(tmp_path: Path):
    """10. Verify hidden files, temp files, secrets, and unsupported extensions are ignored."""
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=secret", encoding="utf-8")
    (tmp_path / ".hidden_note.md").write_text("Hidden markdown", encoding="utf-8")
    (tmp_path / "~$temp_lock.docx").write_bytes(b"lockfile")
    (tmp_path / "credentials.json").write_text('{"key": "secret"}', encoding="utf-8")
    (tmp_path / "database_dump.sql").write_text("SELECT * FROM users;", encoding="utf-8")
    (tmp_path / "private.key").write_text("PRIVATE KEY", encoding="utf-8")
    (tmp_path / "archive.zip").write_bytes(b"PK\x03\x04")
    (tmp_path / "valid_guide.txt").write_text("Approved operational guide.", encoding="utf-8")

    docs = load_documents(base_dir=tmp_path)
    assert len(docs) == 1
    assert docs[0]["source"] == "valid_guide.txt"


def test_11_oversized_files_and_image_limits_handled_safely(tmp_path: Path):
    """11. Verify max_file_size_bytes, max_image_size_bytes, and max_images_per_document limits."""
    (tmp_path / "small.txt").write_text("Compact document text.", encoding="utf-8")
    (tmp_path / "oversized.txt").write_text("X" * 100_000, encoding="utf-8")

    # DOCX with 2 distinct valid images
    docx_path = tmp_path / "two_images.docx"
    doc = docx.Document()
    doc.add_paragraph("Document testing image count cap.")
    doc.add_picture(io.BytesIO(VALID_1X1_PNG))
    doc.add_picture(io.BytesIO(VALID_1X1_JPEG))
    doc.save(str(docx_path))

    # Set max_file_size_bytes=60_000 (skips oversized.txt) and max_images_per_document=1
    docs = load_documents(
        base_dir=tmp_path,
        max_file_size_bytes=60_000,
        max_images_per_document=1,
    )
    sources = {d["source"] for d in docs}
    assert "oversized.txt" not in sources
    assert "small.txt" in sources
    assert "two_images.docx" in sources

    docx_rec = next(d for d in docs if d["source"] == "two_images.docx")
    assert len(docx_rec["image_assets"]) == 1

    # Also verify max_image_size_bytes=10 skips images larger than 10 bytes
    docs_strict_img = load_documents(
        base_dir=tmp_path,
        assets_dir=tmp_path / "_StrictAssets",
        max_file_size_bytes=60_000,
        max_image_size_bytes=10,
    )
    docx_rec_strict = next(d for d in docs_strict_img if d["source"] == "two_images.docx")
    assert docx_rec_strict["image_assets"] == []


def test_12_multiple_documents_load_when_one_is_corrupt(tmp_path: Path):
    """12. Verify multiple valid documents load cleanly even when a sibling file is corrupt."""
    (tmp_path / "01_valid.md").write_text("# First Valid Document", encoding="utf-8")
    (tmp_path / "02_corrupt.pdf").write_bytes(b"NOT_A_PDF")
    (tmp_path / "03_valid.txt").write_text("Second Valid Document", encoding="utf-8")

    docs = load_documents(base_dir=tmp_path)
    assert len(docs) == 2
    assert [d["source"] for d in docs] == ["01_valid.md", "03_valid.txt"]


def test_13_stable_document_ids_across_repeated_loads(tmp_path: Path):
    """13. Verify document_id values are deterministic and identical across repeated calls."""
    (tmp_path / "protocol.md").write_text("Deterministic ID verification text.", encoding="utf-8")
    pdf_path = tmp_path / "paged.pdf"
    _create_synthetic_pdf_with_text_and_images(pdf_path, pages_text=["Page 1", "Page 2"])

    first_load = load_documents(base_dir=tmp_path)
    second_load = load_documents(base_dir=tmp_path)

    assert len(first_load) == 3
    assert [d["document_id"] for d in first_load] == [d["document_id"] for d in second_load]
    # Page 1 and Page 2 of the same PDF must have distinct IDs
    pdf_ids = [d["document_id"] for d in first_load if d["file_type"] == "pdf"]
    assert len(set(pdf_ids)) == 2


def test_14_backward_compatibility_with_document_processor(tmp_path: Path):
    """14. Verify existing callers (e.g., process_documents) work with source, category, and content."""
    sub = tmp_path / "clinical_protocols"
    sub.mkdir()
    (sub / "ventilator_setup.md").write_text(
        "Standardized setup sequence for non-invasive ventilation circuits.",
        encoding="utf-8",
    )

    docs = load_documents(base_dir=tmp_path)
    assert len(docs) == 1
    assert set(["source", "category", "content"]).issubset(docs[0].keys())

    chunks = process_documents(docs, chunk_size=200, overlap=20)
    assert len(chunks) == 1
    assert chunks[0]["source"] == docs[0]["source"]
    assert chunks[0]["category"] == "clinical_protocols"
    assert "non-invasive ventilation circuits" in chunks[0]["content"]
