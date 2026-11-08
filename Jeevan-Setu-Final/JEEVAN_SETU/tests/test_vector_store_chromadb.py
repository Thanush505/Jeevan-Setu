"""
tests/test_vector_store_chromadb.py — Verification Test Suite for Persistent ChromaDB VectorStore.

Tests:
1. Lazy loading & default storage path resolution (`JEEVAN_SETU/vector_storage/`)
2. Persistent ChromaDB initialization & collection creation (`jeevan_setu_knowledge`)
3. Adding document chunks with unique IDs & 384-d embeddings
4. Metadata storage, retrieval, and type/safety validation (blocking nested objects & PHI/UHID)
5. Semantic similarity search (returning document text, metadata, IDs, and distances)
6. Updating existing chunks without creating duplicates
7. Deleting selected chunks by ID
8. Persistence across closing and reopening a new VectorStore client instance
9. Non-destructive preservation of existing files (e.g., index.json) in storage directory
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import chatbot.rag.embedding_service as es
from chatbot.rag.vector_store import (
    DEFAULT_COLLECTION_NAME,
    VECTOR_STORAGE_DIR,
    VectorStore,
    add_document_chunks,
    delete_document_chunks,
    get_collection_count,
    get_collection_info,
    init_vector_store,
    search_similar_chunks,
    update_document_chunks,
    validate_metadata,
)


class TestChromaDBVectorStore(unittest.TestCase):
    """End-to-end tests for Jeevan Setu persistent ChromaDB vector store."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="jeevan_setu_chroma_test_"))
        # Place a pre-existing index.json to verify it is never deleted or overwritten
        cls.legacy_index_path = cls.temp_dir / "index.json"
        cls.legacy_index_path.write_text(json.dumps([{"legacy": True}]), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_default_path_and_collection_configuration(self):
        """Verify default storage path resolves to JEEVAN_SETU/vector_storage and collection name is jeevan_setu_knowledge."""
        self.assertEqual(VECTOR_STORAGE_DIR, BACKEND_ROOT / "vector_storage")
        self.assertEqual(DEFAULT_COLLECTION_NAME, "jeevan_setu_knowledge")

    def test_02_persistent_initialization_and_collection_creation(self):
        """Verify ChromaDB PersistentClient initializes sqlite storage and creates collection."""
        store = init_vector_store(storage_dir=self.temp_dir)
        info = store.get_collection_info()

        self.assertEqual(info["name"], "jeevan_setu_knowledge")
        self.assertEqual(info["count"], 0)
        self.assertEqual(info["embedding_model"], "sentence-transformers/all-MiniLM-L6-v2")
        self.assertEqual(info["embedding_dimension"], 384)
        self.assertTrue((self.temp_dir / "chroma.sqlite3").exists(), "chroma.sqlite3 must be created on disk")
        self.assertTrue(self.legacy_index_path.exists(), "Existing index.json must not be deleted")

    def test_03_add_document_chunks_and_verify_384_dimension(self):
        """Verify adding document chunks stores text, 384-d embeddings, and metadata."""
        docs = [
            "Patients in the Intensive Care Unit (ICU) require continuous hemodynamic monitoring and mechanical ventilation support when indicated.",
            "Step-down transfer from ICU to High Dependency Unit (HDU) requires an Early Warning Score (EWS) below 3 and stable respiratory parameters.",
            "Hospital SOP for sepsis management mandates blood cultures and broad-spectrum antibiotics within the first hour of recognition.",
        ]
        metas = [
            {
                "source": "clinical_protocols/icu_monitoring.md",
                "category": "clinical_protocols",
                "page_number": 1,
                "chunk_index": 0,
                "document_id": "DOC-ICU-001",
            },
            {
                "source": "hospital_sops/icu_to_hdu_transfer.md",
                "category": "hospital_sops",
                "page_number": 2,
                "chunk_index": 1,
                "document_id": "DOC-SOP-002",
            },
            {
                "source": "approved_guidelines/sepsis_bundle.md",
                "category": "approved_guidelines",
                "page_number": 4,
                "chunk_index": 0,
                "document_id": "DOC-GDL-003",
            },
        ]
        ids = ["chunk_icu_1", "chunk_transfer_2", "chunk_sepsis_3"]

        returned_ids = add_document_chunks(
            documents=docs,
            metadatas=metas,
            ids=ids,
            storage_dir=self.temp_dir,
        )
        self.assertEqual(returned_ids, ids)
        self.assertEqual(get_collection_count(storage_dir=self.temp_dir), 3)

        # Inspect underlying ChromaDB stored embeddings to verify 384 dimensions
        store = VectorStore(storage_dir=self.temp_dir)
        col = store.get_or_create_collection()
        stored = col.get(ids=["chunk_icu_1"], include=["embeddings", "metadatas", "documents"])
        stored_emb = stored["embeddings"][0]
        self.assertEqual(len(stored_emb), 384, f"Expected 384-d stored embedding, got {len(stored_emb)}")
        self.assertEqual(stored["metadatas"][0]["document_id"], "DOC-ICU-001")
        self.assertEqual(stored["metadatas"][0]["page_number"], 1)

    def test_04_semantic_search_and_metadata_retrieval(self):
        """Verify semantic search retrieves relevant chunks with text, metadata, IDs, and distances."""
        results = search_similar_chunks(
            query="What are the criteria for transferring a patient from ICU to HDU?",
            top_k=2,
            storage_dir=self.temp_dir,
        )
        self.assertEqual(len(results), 2)

        top_hit = results[0]
        self.assertEqual(top_hit["id"], "chunk_transfer_2")
        self.assertIn("High Dependency Unit (HDU)", top_hit["document"])
        self.assertEqual(top_hit["metadata"]["category"], "hospital_sops")
        self.assertEqual(top_hit["metadata"]["document_id"], "DOC-SOP-002")
        self.assertIsInstance(top_hit["distance"], float)
        self.assertLessEqual(results[0]["distance"], results[1]["distance"])

    def test_05_update_chunks_without_duplicates(self):
        """Verify updating an existing chunk modifies its text and metadata without increasing count."""
        updated_text = (
            "Updated SOP: Step-down transfer from ICU to HDU requires clinician sign-off, "
            "an EWS below 3, and stable oxygenation for at least 12 hours."
        )
        updated_meta = {
            "source": "hospital_sops/icu_to_hdu_transfer_v2.md",
            "category": "hospital_sops",
            "page_number": 3,
            "chunk_index": 1,
            "document_id": "DOC-SOP-002-V2",
        }

        update_document_chunks(
            ids=["chunk_transfer_2"],
            documents=[updated_text],
            metadatas=[updated_meta],
            storage_dir=self.temp_dir,
        )

        # Count must still be 3 (no duplicate created)
        self.assertEqual(get_collection_count(storage_dir=self.temp_dir), 3)

        # Search should return the updated text and updated metadata
        results = search_similar_chunks(
            query="clinician sign-off and 12 hours stable oxygenation for HDU transfer",
            top_k=1,
            storage_dir=self.temp_dir,
        )
        self.assertEqual(results[0]["id"], "chunk_transfer_2")
        self.assertIn("Updated SOP", results[0]["document"])
        self.assertEqual(results[0]["metadata"]["document_id"], "DOC-SOP-002-V2")
        self.assertEqual(results[0]["metadata"]["page_number"], 3)

    def test_06_delete_selected_chunks_by_id(self):
        """Verify deleting a chunk by ID removes it and decrements collection count."""
        delete_document_chunks(ids=["chunk_sepsis_3"], storage_dir=self.temp_dir)
        self.assertEqual(get_collection_count(storage_dir=self.temp_dir), 2)

        store = VectorStore(storage_dir=self.temp_dir)
        all_Ids = [item["id"] for item in store.get_all()]
        self.assertNotIn("chunk_sepsis_3", all_Ids)
        self.assertIn("chunk_icu_1", all_Ids)
        self.assertIn("chunk_transfer_2", all_Ids)

    def test_07_persistence_across_reopened_client_instances(self):
        """Verify data persists on disk after closing/discarding client and opening a fresh instance."""
        reopened_store = VectorStore(storage_dir=self.temp_dir, collection_name=DEFAULT_COLLECTION_NAME)
        self.assertEqual(reopened_store.get_collection_count(), 2)

        info = get_collection_info(storage_dir=self.temp_dir)
        self.assertEqual(info["count"], 2)

        hits = reopened_store.search("mechanical ventilation and hemodynamic monitoring in ICU", top_k=1)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], "chunk_icu_1")

        # Verify legacy index.json is still intact
        self.assertEqual(
            json.loads(self.legacy_index_path.read_text(encoding="utf-8")),
            [{"legacy": True}],
        )

    def test_08_metadata_and_patient_safety_validation(self):
        """Verify nested objects and patient-identifiable data (UHID / patient_id) are rejected."""
        # Reject nested dict/list in metadata
        with self.assertRaises(ValueError):
            validate_metadata({"source": "doc.md", "nested": {"bad": 1}})
        with self.assertRaises(ValueError):
            validate_metadata({"source": "doc.md", "tags": ["a", "b"]})

        # Reject prohibited patient metadata keys
        with self.assertRaises(ValueError):
            validate_metadata({"source": "doc.md", "patient_id": 1})
        with self.assertRaises(ValueError):
            validate_metadata({"source": "doc.md", "ews_score": 7})

        # Reject UHID in document text
        store = VectorStore(storage_dir=self.temp_dir)
        with self.assertRaises(ValueError):
            store.add_documents(
                documents=["Patient Rajesh Kumar UHID-2026-00001 has EWS 7."],
                metadatas=[{"source": "leak.md", "category": "general"}],
                ids=["bad_phi_chunk"],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)

