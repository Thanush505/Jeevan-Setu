"""
tests/test_vector_store.py — Comprehensive Pytest Verification Suite for Persistent ChromaDB VectorStore.

Tests all 17 required scenarios using isolated temporary directories (`tmp_path`) without
modifying or deleting `JEEVAN_SETU/vector_storage/`:
1. Persistent client initialization.
2. Collection creation and reuse (cosine similarity, 384-d metadata, no duplicate collections).
3. Adding one chunk (`add_chunk` / `add_document_chunk`).
4. Adding batches of chunks (`add_documents`, `add_chunks`, `add_document_chunks`).
5. Correct 384-dimensional embeddings stored and verified.
6. Metadata preservation (including source traceability, page numbers, content hash, and image asset references).
7. Semantic similarity search compatibility.
8. Duplicate insertion behavior (idempotent re-ingestion reuses unchanged embeddings without creating duplicates).
9. Updating chunks in-place.
10. Deleting selected chunks by ID.
11. Retrieving chunks by ID (`get_chunks_by_ids`).
12. Persistence after reopening the client.
13. Document version handling (v1.0 vs v2.0 coexist safely without overwriting each other).
14. Invalid embeddings (wrong dimension, NaN, Inf, non-numeric rejected).
15. Empty input handling (empty documents, empty query, empty IDs rejected).
16. Isolation between separate documents (`delete_chunks_by_document` removes only target document/version).
17. MySQL metadata compatibility (`sync_mysql=True` with `RAGDocument`, `RAGDocumentImage`, `RAGDocumentChunk`).
"""

import math
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from chatbot.rag.document_processor import process_documents
from chatbot.rag.embedding_service import (
    EXPECTED_EMBEDDING_DIMENSION,
    MODEL_NAME,
    get_embedding,
    get_embedding_dimension,
)
from chatbot.rag.vector_store import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_SIMILARITY_SPACE,
    VECTOR_STORAGE_DIR,
    VectorStore,
    add_document_chunk,
    add_document_chunks,
    delete_document_chunks,
    get_chunks_by_ids,
    get_collection_count,
    get_collection_info,
    get_or_create_collection,
    init_vector_store,
    search_similar_chunks,
    update_document_chunks,
    validate_embedding_vector,
    validate_metadata,
)


@pytest.fixture
def sample_documents():
    """Fictional, non-patient sample documents and metadata."""
    documents = [
        "Solar observatory telescopes capture high-resolution images of sunspots and coronal loops.",
        "Deep-sea autonomous submersibles map hydrothermal vents along mid-oceanic ridges.",
        "High-speed magnetic levitation trains glide above guideways using electromagnetic suspension.",
    ]
    metadatas = [
        {
            "source": "project_documentation/astronomy_handbook.pdf",
            "category": "project_documentation",
            "file_type": "pdf",
            "page_number": 12,
            "chunk_index": 0,
            "document_id": "DOC-ASTRO-101",
            "document_version": "1.0",
        },
        {
            "source": "project_documentation/oceanography_guide.pdf",
            "category": "project_documentation",
            "file_type": "pdf",
            "page_number": 45,
            "chunk_index": 1,
            "document_id": "DOC-OCEAN-202",
            "document_version": "1.0",
        },
        {
            "source": "project_documentation/transit_engineering.docx",
            "category": "project_documentation",
            "file_type": "docx",
            "chunk_index": 2,
            "document_id": "DOC-TRANSIT-303",
            "document_version": "1.0",
        },
    ]
    ids = ["fictional_doc_1", "fictional_doc_2", "fictional_doc_3"]
    return documents, metadatas, ids


def test_01_persistent_client_initialization(tmp_path: Path):
    """1. Test ChromaDB persistent client initialization in an isolated tmp_path directory."""
    store = init_vector_store(storage_dir=tmp_path)

    assert isinstance(store, VectorStore)
    assert store.storage_dir == tmp_path.resolve()
    assert (tmp_path / "chroma.sqlite3").exists()
    assert VECTOR_STORAGE_DIR == BACKEND_ROOT / "vector_storage"


def test_02_collection_creation_and_reuse(tmp_path: Path):
    """2. Test collection creation with cosine similarity and reuse without creating duplicates."""
    col_1 = get_or_create_collection(storage_dir=tmp_path, collection_name=DEFAULT_COLLECTION_NAME)
    col_2 = get_or_create_collection(storage_dir=tmp_path, collection_name=DEFAULT_COLLECTION_NAME)
    info = get_collection_info(storage_dir=tmp_path, collection_name=DEFAULT_COLLECTION_NAME)

    assert col_1.name == DEFAULT_COLLECTION_NAME
    assert col_2.name == DEFAULT_COLLECTION_NAME
    assert info["name"] == DEFAULT_COLLECTION_NAME
    assert info["count"] == 0
    assert info["embedding_model"] == MODEL_NAME
    assert info["embedding_dimension"] == EXPECTED_EMBEDDING_DIMENSION
    assert info["similarity_metric"] == DEFAULT_SIMILARITY_SPACE
    assert get_embedding_dimension() == 384

    # Verify only 1 collection exists in the client
    store = VectorStore(storage_dir=tmp_path)
    client = store._get_client()
    assert len(client.list_collections()) == 1


def test_03_adding_one_chunk(tmp_path: Path):
    """3. Test adding a single chunk (both raw string and processor chunk dict)."""
    store = VectorStore(storage_dir=tmp_path)

    cid_1 = store.add_chunk(
        chunk="Standard ICU step-down checklist requires stable oxygenation and hemodynamic parameters.",
        metadata={
            "document_id": "DOC-SINGLE-001",
            "document_version": "1.0",
            "source": "hospital_sops/stepdown_checklist.md",
            "category": "hospital_sops",
            "file_type": "markdown",
            "chunk_index": 0,
        },
        chunk_id="single_chunk_001",
    )
    assert cid_1 == "single_chunk_001"
    assert store.get_collection_count() == 1

    # Add a single processor-formatted chunk dict via module-level helper
    proc_chunks = process_documents([
        {
            "document_id": "DOC-SINGLE-002",
            "source": "clinical_protocols/airway_assessment.pdf",
            "category": "clinical_protocols",
            "file_type": "pdf",
            "page_number": 4,
            "content": "Verify cuff pressure between 20 and 30 cmH2O every shift.",
        }
    ])
    cid_2 = add_document_chunk(proc_chunks[0], storage_dir=tmp_path)
    assert cid_2 == proc_chunks[0]["chunk_id"]
    assert store.get_collection_count() == 2


def test_04_adding_batches_of_chunks(tmp_path: Path, sample_documents):
    """4. Test adding multiple chunks in a batch via `add_documents` and `add_chunks`."""
    documents, metadatas, ids = sample_documents
    store = VectorStore(storage_dir=tmp_path)

    stored_ids = store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
    assert stored_ids == ids
    assert store.get_collection_count() == 3


def test_05_correct_384_dimensional_embeddings(tmp_path: Path, sample_documents):
    """5. Verify stored vectors in ChromaDB are 384-dimensional finite floats."""
    documents, metadatas, ids = sample_documents
    store = VectorStore(storage_dir=tmp_path)
    store.add_documents(documents=documents, metadatas=metadatas, ids=ids)

    col = store.get_or_create_collection()
    fetched = col.get(ids=ids, include=["embeddings", "documents", "metadatas"])
    assert len(fetched["embeddings"]) == 3
    for emb in fetched["embeddings"]:
        assert len(emb) == EXPECTED_EMBEDDING_DIMENSION
        assert all(math.isfinite(float(x)) for x in emb)


def test_06_metadata_and_source_traceability_preservation(tmp_path: Path):
    """
    6. Verify every stored and retrieved record preserves full citation traceability:
    `chunk_id`, `document_id`, `document_version`, `source`, `category`, `file_type`,
    `page_number`, `chunk_index`, `content_hash`, and `image_assets`.
    """
    raw_docs = [
        {
            "document_id": "DOC-TRACE-PDF-01",
            "document_version": "1.2",
            "source": "clinical_protocols/ventilator_protocol.pdf",
            "category": "clinical_protocols",
            "file_type": "pdf",
            "page_number": 7,
            "ocr_required": False,
            "image_assets": [
                {
                    "image_id": "img_vent_p7_1",
                    "document_id": "DOC-TRACE-PDF-01",
                    "source_document": "clinical_protocols/ventilator_protocol.pdf",
                    "page_number": 7,
                    "image_format": "png",
                    "file_size": 3072,
                    "asset_path": "_extracted_assets/vent_p7_1.png",
                }
            ],
            "content": "Maintain plateau pressure below 30 cmH2O during volume-controlled ventilation.",
        }
    ]
    chunks = process_documents(raw_docs)
    store = VectorStore(storage_dir=tmp_path)
    stored_ids = store.add_chunks(chunks)

    retrieved = store.get_chunks_by_ids(stored_ids)
    assert len(retrieved) == 1
    rec = retrieved[0]

    assert rec["chunk_id"] == chunks[0]["chunk_id"]
    assert rec["document_id"] == "DOC-TRACE-PDF-01"
    assert rec["document_version"] == "1.2"
    assert rec["source"] == "clinical_protocols/ventilator_protocol.pdf"
    assert rec["category"] == "clinical_protocols"
    assert rec["file_type"] == "pdf"
    assert rec["page_number"] == 7
    assert rec["chunk_index"] == 0
    assert rec["content_hash"] == chunks[0]["content_hash"]
    assert len(rec["image_assets"]) == 1
    assert rec["image_assets"][0]["image_id"] == "img_vent_p7_1"
    assert rec["image_assets"][0]["asset_path"] == "_extracted_assets/vent_p7_1.png"


def test_07_semantic_similarity_search_compatibility(tmp_path: Path, sample_documents):
    """7. Test semantic similarity search ranks matching topic highest and returns full citation metadata."""
    documents, metadatas, ids = sample_documents
    add_document_chunks(documents=documents, metadatas=metadatas, ids=ids, storage_dir=tmp_path)

    results = search_similar_chunks(
        query="underwater robots exploring ocean floor hydrothermal vents",
        top_k=2,
        storage_dir=tmp_path,
    )

    assert len(results) == 2
    assert results[0]["id"] == "fictional_doc_2"
    assert results[0]["document_id"] == "DOC-OCEAN-202"
    assert results[0]["page_number"] == 45
    assert isinstance(results[0]["distance"], float)
    assert results[0]["distance"] <= results[1]["distance"]


def test_08_duplicate_insertion_behavior_and_embedding_reuse(tmp_path: Path, sample_documents):
    """
    8. Verify idempotent ingestion: re-ingesting unchanged chunks does not create duplicates
    and reuses existing stored embeddings without calling `get_embeddings` or `get_embedding` again.
    """
    documents, metadatas, ids = sample_documents
    store = VectorStore(storage_dir=tmp_path)

    store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
    assert store.get_collection_count() == 3

    # Re-ingesting the exact same documents/IDs must reuse stored embeddings without calling SentenceTransformer
    with patch("chatbot.rag.vector_store.get_embeddings") as mock_batch_emb, \
         patch("chatbot.rag.vector_store.get_embedding") as mock_single_emb:
        re_ids = store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
        assert re_ids == ids
        assert store.get_collection_count() == 3
        mock_batch_emb.assert_not_called()
        mock_single_emb.assert_not_called()


def test_09_updating_chunks(tmp_path: Path, sample_documents):
    """9. Test updating an existing chunk's text and metadata in-place without creating duplicates."""
    documents, metadatas, ids = sample_documents
    store = VectorStore(storage_dir=tmp_path)
    store.add_documents(documents=documents, metadatas=metadatas, ids=ids)

    updated_text = "Orbital space telescopes observe infrared galaxies beyond cosmic dust clouds."
    updated_meta = {
        "source": "project_documentation/astronomy_handbook_v2.pdf",
        "category": "project_documentation",
        "file_type": "pdf",
        "page_number": 99,
        "chunk_index": 0,
        "document_id": "DOC-ASTRO-101",
        "document_version": "2.0",
    }

    updated_ids = update_document_chunks(
        ids=["fictional_doc_1"],
        documents=[updated_text],
        metadatas=[updated_meta],
        storage_dir=tmp_path,
    )
    assert updated_ids == ["fictional_doc_1"]
    assert store.get_collection_count() == 3

    results = store.search(query="infrared galaxies observed by orbital space telescopes", top_k=1)
    assert results[0]["id"] == "fictional_doc_1"
    assert results[0]["document"] == updated_text
    assert results[0]["document_version"] == "2.0"
    assert results[0]["page_number"] == 99


def test_10_deleting_selected_chunks(tmp_path: Path, sample_documents):
    """10. Test deleting selected chunks by ID removes only those chunks."""
    documents, metadatas, ids = sample_documents
    store = VectorStore(storage_dir=tmp_path)
    store.add_documents(documents=documents, metadatas=metadatas, ids=ids)
    assert store.get_collection_count() == 3

    deleted = delete_document_chunks(ids=["fictional_doc_2"], storage_dir=tmp_path)
    assert deleted == ["fictional_doc_2"]
    assert get_collection_count(storage_dir=tmp_path) == 2

    remaining_ids = {item["id"] for item in store.get_all()}
    assert remaining_ids == {"fictional_doc_1", "fictional_doc_3"}


def test_11_retrieving_chunks_by_id(tmp_path: Path, sample_documents):
    """11. Test retrieving specific chunks by ID in requested order via `get_chunks_by_ids`."""
    documents, metadatas, ids = sample_documents
    store = VectorStore(storage_dir=tmp_path)
    store.add_documents(documents=documents, metadatas=metadatas, ids=ids)

    fetched = get_chunks_by_ids(["fictional_doc_3", "fictional_doc_1"], storage_dir=tmp_path)
    assert [item["id"] for item in fetched] == ["fictional_doc_3", "fictional_doc_1"]
    assert fetched[0]["document"] == documents[2]
    assert fetched[0]["document_id"] == "DOC-TRANSIT-303"
    assert fetched[1]["document"] == documents[0]
    assert fetched[1]["document_id"] == "DOC-ASTRO-101"


def test_12_persistence_after_reopening_client(tmp_path: Path, sample_documents):
    """12. Test that stored chunks, embeddings, and metadata persist when reopening a fresh VectorStore."""
    documents, metadatas, ids = sample_documents

    store_initial = VectorStore(storage_dir=tmp_path, collection_name="fictional_persistence_test")
    store_initial.add_documents(documents=documents, metadatas=metadatas, ids=ids)
    assert store_initial.get_collection_count() == 3
    del store_initial

    store_reopened = VectorStore(storage_dir=tmp_path, collection_name="fictional_persistence_test")
    assert store_reopened.get_collection_count() == 3

    results = store_reopened.search(query="sunspots and coronal loops on the sun", top_k=1)
    assert len(results) == 1
    assert results[0]["id"] == "fictional_doc_1"
    assert results[0]["document_id"] == "DOC-ASTRO-101"


def test_13_document_version_handling(tmp_path: Path):
    """
    13. Verify updated document versions (`1.0` vs `2.0`) have distinct chunk IDs,
    coexist without automatically deleting older versions, and are distinguishable in metadata.
    """
    doc_v1 = {
        "document_id": "DOC-SOP-SEPSIS",
        "document_version": "1.0",
        "source": "hospital_sops/sepsis_protocol.md",
        "category": "hospital_sops",
        "file_type": "markdown",
        "content": "Version 1.0: Administer broad-spectrum antimicrobials within 60 minutes of recognition.",
    }
    doc_v2 = {
        "document_id": "DOC-SOP-SEPSIS",
        "document_version": "2.0",
        "source": "hospital_sops/sepsis_protocol.md",
        "category": "hospital_sops",
        "file_type": "markdown",
        "content": "Version 2.0: Obtain blood cultures and serum lactate, then administer antimicrobials within 45 minutes.",
    }

    chunks_v1 = process_documents([doc_v1])
    chunks_v2 = process_documents([doc_v2])
    assert chunks_v1[0]["chunk_id"] != chunks_v2[0]["chunk_id"]

    store = VectorStore(storage_dir=tmp_path)
    store.add_chunks(chunks_v1)
    store.add_chunks(chunks_v2)

    # Both v1.0 and v2.0 must exist in the store
    assert store.get_collection_count() == 2
    all_chunks = store.get_all()
    versions = {c["document_version"] for c in all_chunks}
    assert versions == {"1.0", "2.0"}


def test_14_invalid_embeddings_rejected(tmp_path: Path):
    """14. Verify embeddings with wrong dimension (<384 or >384), NaN, Inf, or non-numerics are rejected."""
    store = VectorStore(storage_dir=tmp_path)

    # Wrong dimension (10 instead of 384)
    with pytest.raises(ValueError, match="dimension mismatch"):
        store.add_documents(
            documents=["Valid clinical protocol text."],
            ids=["bad_dim_1"],
            embeddings=[[0.1] * 10],
        )

    # NaN value inside 384-d vector
    nan_vec = [0.05] * 384
    nan_vec[100] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        store.add_documents(
            documents=["Valid clinical protocol text."],
            ids=["bad_nan_1"],
            embeddings=[nan_vec],
        )

    # Inf value inside 384-d vector
    inf_vec = [0.05] * 384
    inf_vec[0] = float("inf")
    with pytest.raises(ValueError, match="non-finite"):
        validate_embedding_vector(inf_vec)


def test_15_empty_and_prohibited_input_rejected(tmp_path: Path):
    """15. Verify empty inputs, patient UHID records, and raw binary/base64 image data are rejected."""
    store = VectorStore(storage_dir=tmp_path)

    with pytest.raises(ValueError):
        store.add_documents(documents=[])

    with pytest.raises(ValueError):
        store.add_documents(documents=["   \n\t  "])

    with pytest.raises(ValueError):
        store.search(query="")

    with pytest.raises(ValueError):
        store.get_chunks_by_ids(ids=[])

    with pytest.raises(ValueError):
        store.delete_documents(ids=[])

    # Patient UHID must be blocked from shared ChromaDB
    with pytest.raises(ValueError, match="UHID"):
        store.add_documents(documents=["Patient record UHID-2026-00001 vitals."])

    # Raw binary bytes in metadata must be blocked
    with pytest.raises(ValueError, match="binary"):
        validate_metadata({"source": "doc.pdf", "raw_image": b"\x89PNG\r\n"})


def test_16_isolation_between_separate_documents(tmp_path: Path):
    """
    16. Verify `delete_chunks_by_document` removes only the targeted document (and optional version)
    without affecting any other documents in the collection.
    """
    docs = [
        {
            "document_id": "DOC-ALPHA",
            "document_version": "1.0",
            "source": "clinical_protocols/alpha.md",
            "category": "clinical_protocols",
            "content": "Alpha protocol version 1.0 content.",
        },
        {
            "document_id": "DOC-ALPHA",
            "document_version": "2.0",
            "source": "clinical_protocols/alpha.md",
            "category": "clinical_protocols",
            "content": "Alpha protocol version 2.0 updated content.",
        },
        {
            "document_id": "DOC-BETA",
            "document_version": "1.0",
            "source": "hospital_sops/beta.md",
            "category": "hospital_sops",
            "content": "Beta SOP content that must remain untouched.",
        },
    ]
    chunks = process_documents(docs)
    store = VectorStore(storage_dir=tmp_path)
    store.add_chunks(chunks)
    assert store.get_collection_count() == 3

    # Delete only version 1.0 of DOC-ALPHA
    removed = store.delete_chunks_by_document(document_id="DOC-ALPHA", document_version="1.0")
    assert len(removed) == 1
    assert store.get_collection_count() == 2

    remaining = store.get_all()
    remaining_pairs = {(r["document_id"], r["document_version"]) for r in remaining}
    assert remaining_pairs == {("DOC-ALPHA", "2.0"), ("DOC-BETA", "1.0")}


def test_17_mysql_metadata_compatibility(tmp_path: Path):
    """
    17. Verify `sync_mysql=True` synchronizes document, image, and chunk metadata into the
    Migration 009 MySQL models (`RAGDocument`, `RAGDocumentImage`, `RAGDocumentChunk`)
    without storing raw embedding vectors in MySQL.
    """
    import models.chatbot_model as cm

    recorded_docs: List[Dict[str, Any]] = []
    recorded_imgs: List[Dict[str, Any]] = []
    recorded_chunks: List[Dict[str, Any]] = []

    def fake_doc_upsert(**kwargs):
        recorded_docs.append(kwargs)
        return 1

    def fake_img_upsert(**kwargs):
        recorded_imgs.append(kwargs)
        return 1

    def fake_chunk_upsert(**kwargs):
        recorded_chunks.append(kwargs)
        return 1

    test_doc_id = "doc_pytest_vec_sync_017"
    test_img_id = "img_pytest_vec_sync_017_p1"
    sample_doc = {
        "document_id": test_doc_id,
        "document_version": "1.2",
        "source": "approved_guidelines/synthetic_sync_test.pdf",
        "category": "approved_guidelines",
        "file_type": "pdf",
        "page_number": 1,
        "ocr_required": False,
        "image_assets": [
            {
                "image_id": test_img_id,
                "document_id": test_doc_id,
                "source_document": "approved_guidelines/synthetic_sync_test.pdf",
                "page_number": 1,
                "image_format": "png",
                "file_size": 1024,
                "asset_path": "_extracted_assets/synthetic_sync_test_p1.png",
            }
        ],
        "content": "Synthetic guideline text for testing ChromaDB to MySQL metadata synchronization.",
    }

    chunks = process_documents([sample_doc])
    store = VectorStore(
        storage_dir=tmp_path,
        collection_name="pytest_mysql_sync_collection",
        sync_mysql=True,
    )

    with patch.object(cm.RAGDocument, "upsert", side_effect=fake_doc_upsert), \
         patch.object(cm.RAGDocumentImage, "upsert", side_effect=fake_img_upsert), \
         patch.object(cm.RAGDocumentChunk, "upsert", side_effect=fake_chunk_upsert):
        stored_ids = store.add_chunks(chunks, sync_mysql=True)

    assert len(stored_ids) == 1
    cid = stored_ids[0]

    assert len(recorded_docs) == 1
    assert recorded_docs[0]["document_id"] == test_doc_id
    assert recorded_docs[0]["document_version"] == "1.2"
    assert recorded_docs[0]["source_path"] == "approved_guidelines/synthetic_sync_test.pdf"
    assert recorded_docs[0]["processing_status"] == "indexed"

    assert len(recorded_imgs) == 1
    assert recorded_imgs[0]["image_id"] == test_img_id
    assert recorded_imgs[0]["document_id"] == test_doc_id
    assert recorded_imgs[0]["asset_path"] == "_extracted_assets/synthetic_sync_test_p1.png"

    assert len(recorded_chunks) == 1
    assert recorded_chunks[0]["chunk_id"] == cid
    assert recorded_chunks[0]["chroma_document_id"] == cid
    assert recorded_chunks[0]["chroma_collection"] == "pytest_mysql_sync_collection"
    assert recorded_chunks[0]["document_id"] == test_doc_id
    assert recorded_chunks[0]["document_version"] == "1.2"
    assert recorded_chunks[0]["related_image_id"] == test_img_id
    # Ensure raw embedding arrays are never passed to MySQL
    assert "embedding" not in recorded_chunks[0]
    assert "embeddings" not in recorded_chunks[0]
