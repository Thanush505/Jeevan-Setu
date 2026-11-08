"""
tests/test_image_processor.py

Pytest suite for Jeevan Setu Multimodal Image Processor (`chatbot/vision/image_processor.py`).

Tests:
1. PDF image processing preserves `document_id`, `image_id`, `source_document`, and `page_number`.
2. DOCX image processing preserves `document_id`, `image_id`, and `source_document` with `page_number=None` (never inventing page numbers).
3. Duplicate image detection (`content_hash` deduplication skips redundant OCR/Vision calls).
4. Searchable text generation combining OCR and AI-generated visual descriptions.
"""

import io
import json
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image, ImageDraw

from chatbot.vision.image_processor import (
    process_knowledge_image_asset,
)


def _write_synthetic_asset(assets_dir: Path, filename: str, label: str = "EWS CHART") -> str:
    assets_dir.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (320, 120), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), label, fill="black", font_size=24)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    target = assets_dir / filename
    target.write_bytes(buf.getvalue())
    return f"_extracted_assets/{filename}"


def test_01_pdf_and_docx_image_traceability_and_deduplication(tmp_path: Path):
    assets_dir = tmp_path / "_extracted_assets"
    rel_pdf_asset = _write_synthetic_asset(assets_dir, "pdf_p4_img1.png", "ICU FLOW")

    ocr_spy = MagicMock(return_value=([[[[10, 10], [100, 10], [100, 30], [10, 30]], "ICU FLOW", 0.99]], 0.01))
    vision_spy = MagicMock(return_value={
        "success": True,
        "model": "google/gemma-4-31b-it:free",
        "message": {
            "role": "assistant",
            "content": json.dumps({
                "summary": "Diagram of ICU step-down workflow.",
                "content_type": "diagram",
                "visible_labels": ["ICU FLOW"],
                "visible_elements": ["Process box"],
                "layout_and_relationships": "Single stage box",
                "uncertainty_notes": "None",
            }),
        },
    })

    seen_hashes = {}

    # 1. Process PDF extracted image (page_number=4 must be preserved)
    pdf_res = process_knowledge_image_asset(
        {
            "image_id": "img_pdf_p4_1",
            "document_id": "doc_pdf_guideline_p4",
            "source_document": "approved_guidelines/icu_protocol.pdf",
            "page_number": 4,
            "image_index": 1,
            "asset_path": rel_pdf_asset,
        },
        base_dir=tmp_path,
        ocr_backend=ocr_spy,
        vision_caller=vision_spy,
        seen_hashes=seen_hashes,
        sync_mysql=False,
    )

    assert pdf_res["processing_status"] == "completed"
    assert pdf_res["document_id"] == "doc_pdf_guideline_p4"
    assert pdf_res["image_id"] == "img_pdf_p4_1"
    assert pdf_res["page_number"] == 4
    assert pdf_res["ocr_status"] == "completed"
    assert pdf_res["vision_status"] == "completed"
    assert pdf_res["ai_generated_description"] is True
    assert pdf_res["duplicate_skipped"] is False
    assert "ICU FLOW" in pdf_res["searchable_text"]
    assert "[AI-Generated Visual Description (diagram)]" in pdf_res["searchable_text"]
    assert ocr_spy.call_count == 1
    assert vision_spy.call_count == 1

    # 2. Process duplicate image from DOCX (page_number=None must be preserved; OCR/Vision skipped via hash cache)
    docx_res = process_knowledge_image_asset(
        {
            "image_id": "img_docx_1",
            "document_id": "doc_sop_docx",
            "source_document": "hospital_sops/handoff_sop.docx",
            "page_number": None,
            "image_index": 1,
            "asset_path": rel_pdf_asset,
        },
        base_dir=tmp_path,
        ocr_backend=ocr_spy,
        vision_caller=vision_spy,
        seen_hashes=seen_hashes,
        sync_mysql=False,
    )

    assert docx_res["duplicate_skipped"] is True
    assert docx_res["document_id"] == "doc_sop_docx"
    assert docx_res["page_number"] is None
    # OCR and Vision were NOT called a second time for the identical image hash
    assert ocr_spy.call_count == 1
    assert vision_spy.call_count == 1

