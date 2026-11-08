"""
tests/test_multimodal_ingestion.py

End-to-end pytest suite for Jeevan Setu Multimodal Knowledge Ingestion & Retrieval
(`chatbot/vision/image_processor.py`, `chatbot/rag/vector_store.py`,
`chatbot/rag/retriever.py`, `chatbot/rag/context_builder.py`).

Tests:
1. Full ingestion of PDF and DOCX documents with embedded images into a temporary
   ChromaDB `VectorStore`.
2. OCR text and AI-generated visual descriptions are indexed as searchable text
   chunks in ChromaDB.
3. No raw image bytes or base64 data URLs are stored in ChromaDB.
4. Retrieval (`retrieve_relevant_chunks`) and Context Builder (`build_general_chat_context`)
   preserve `document_id`, `image_id`, `source`, `page_number`, `ocr_status`,
   `vision_status`, `content_type`, and `ai_generated_description`.
"""

import io
import json
from pathlib import Path
from PIL import Image, ImageDraw

from chatbot.rag.context_builder import build_general_chat_context
from chatbot.rag.document_loader import load_documents
from chatbot.rag.retriever import retrieve_relevant_chunks
from chatbot.rag.vector_store import VectorStore
from chatbot.vision.image_processor import ingest_knowledge_document_images


def _create_docx_with_embedded_png(docx_path: Path, text_paragraph: str, img_label: str) -> None:
    import docx

    doc = docx.Document()
    doc.add_heading("Synthetic HDU Step-Down SOP", level=1)
    doc.add_paragraph(text_paragraph)

    img = Image.new("RGB", (360, 120), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 40), img_label, fill="black", font_size=24)
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    doc.add_picture(img_buf)
    doc.save(str(docx_path))


def test_01_multimodal_ingestion_indexing_and_retrieval_without_raw_bytes_in_chromadb(tmp_path: Path):
    kb_dir = tmp_path / "knowledge_base"
    sop_dir = kb_dir / "hospital_sops"
    sop_dir.mkdir(parents=True)

    docx_file = sop_dir / "synthetic_stepdown_sop.docx"
    _create_docx_with_embedded_png(
        docx_file,
        "Standard operating procedure for ICU to HDU transfer handoff verification.",
        "CAPNOGRAPHY WAVEFORM NORMAL 38 MMHG",
    )

    # 1. Load document and extract embedded image via `document_loader.load_documents`
    docs = load_documents(kb_dir)
    assert len(docs) == 1
    assert len(docs[0]["image_assets"]) == 1
    assert docs[0]["page_number"] is None  # DOCX does not invent page numbers

    # 2. Initialize isolated temporary ChromaDB VectorStore
    chroma_dir = tmp_path / "temp_chroma"
    store = VectorStore(storage_dir=chroma_dir)

    mock_vision_caller = lambda **kw: {
        "success": True,
        "model": "google/gemma-4-31b-it:free",
        "message": {
            "role": "assistant",
            "content": json.dumps({
                "summary": "Capnography waveform reference chart showing normal end-tidal CO2 of 38 mmHg.",
                "content_type": "chart",
                "visible_labels": ["ETCO2 38 mmHg", "Phase III Plateau"],
                "visible_elements": ["Capnogram curve"],
                "layout_and_relationships": "Time on horizontal axis, CO2 mmHg on vertical axis.",
                "uncertainty_notes": "None",
            }),
        },
    }

    # 3. Run Multimodal Knowledge Ingestion
    ingest_res = ingest_knowledge_document_images(
        docs,
        base_dir=kb_dir,
        vector_store=store,
        vision_caller=mock_vision_caller,
        sync_mysql=False,
    )

    assert ingest_res["images_processed"] == 1
    assert ingest_res["chunks_created"] >= 1
    assert ingest_res["vector_store_summary"]["added"] >= 1

    # Verify no raw image bytes or base64 strings were stored in ChromaDB
    for ch in ingest_res["chunks"]:
        assert "data:image/" not in ch["content"]
        assert ";base64," not in ch["content"]
        assert ch["metadata"]["image_id"] is not None
        assert ch["metadata"]["ocr_status"] == "completed"
        assert ch["metadata"]["vision_status"] == "completed"
        assert ch["metadata"]["content_type"] == "chart"
        assert ch["metadata"]["ai_generated_description"] is True

    # 4. Retrieve via `retrieve_relevant_chunks` and build context via `build_general_chat_context`
    retrieved = retrieve_relevant_chunks(
        "What does the capnography waveform chart show for normal end-tidal CO2?",
        top_k=3,
        store=store,
        min_relevance=0.1,
    )
    assert len(retrieved) >= 1
    top_hit = retrieved[0]
    assert "38" in top_hit["content"]
    assert top_hit["metadata"]["vision_status"] == "completed"
    assert top_hit["metadata"]["ai_generated_description"] is True

    ctx = build_general_chat_context(
        question="Explain the capnography waveform reference chart.",
        user_id=10,
        user_role="doctor",
        pre_retrieved_chunks=retrieved,
    )
    ctx_chunk = ctx["knowledge_context"]["chunks"][0]
    assert ctx_chunk["image_id"] is not None
    assert ctx_chunk["ocr_status"] == "completed"
    assert ctx_chunk["vision_status"] == "completed"
    assert ctx_chunk["content_type"] == "chart"
    assert ctx_chunk["ai_generated_description"] is True

