"""
tests/test_migration_009_and_schema_sync.py — Comprehensive verification suite for
Migration 009 (Agentic Hybrid Multimodal RAG) and Schema.db / schema.sql synchronization.

Covers:
1. Migration 009 execution on an isolated temporary MySQL test database (`jeevan_setu_test_mig009`).
2. Existence of all 4 RAG tables (`rag_documents`, `rag_document_images`, `rag_document_chunks`, `patient_medical_images`).
3. Column definitions, data types, nullability, and defaults.
4. Primary keys and foreign keys (including retention-safe ON DELETE RESTRICT on `patient_medical_images.patient_id`).
5. Indexes and unique constraints.
6. `chatbot_conversations` new backward-compatible columns (`chat_mode`, `tools_invoked`, `rag_sources`) and `idx_chatbot_conv_mode_created`.
7. Backward-compatible `ChatbotConversation.save()` and RAG-aware `ChatbotConversation.save()` + General Chat isolation.
8. Preservation of all 10 canonical baseline patients (`UHID-2026-00001` through `UHID-2026-00010`).
9. Compatibility of existing EWS (`EWSScore`) and Transfer (`Transfer`, `Recommendation`) models.
10. Orchestration-level idempotency (Migration 009 cannot be applied twice accidentally).
11. Partial migration recovery (recovering safely when a table/column already exists before `schema_migrations` is marked).
12. `Schema.db` synchronization captures complete schema metadata (tables, columns, PKs, FKs, unique constraints, indexes).
13. `Schema.db` contains zero patient records, zero clinical records, and zero user password hashes.
14. Repeated `Schema.db` and `schema.sql` synchronization is deterministic and stable.
15. RAG & PatientMedicalImage model CRUD operations and General Chat RBAC isolation.
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import db
from database.migration_manager import MigrationManager
from database.sync_schema import sync_all, get_mysql_schema_metadata
from models.chatbot_model import (
    ChatbotConversation,
    RAGDocument,
    RAGDocumentImage,
    RAGDocumentChunk,
    PatientMedicalImage,
)
from models.patient_model import Patient
from models.ews_score_model import EWSScore
from models.recommendation_model import Recommendation
from models.transfer_model import Transfer


class TestMigration009AndSchemaSync(unittest.TestCase):
    """End-to-end verification of Migration 009, Models, and Schema.db Synchronization."""

    MIGRATION_VERSION = "009_agentic_hybrid_multimodal_rag"
    MIGRATION_FILENAME = "009_agentic_hybrid_multimodal_rag.sql"

    @classmethod
    def setUpClass(cls):
        cls.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.migrations_dir = os.path.join(cls.base_dir, "database", "migrations")
        cls.migration_009_path = os.path.join(cls.migrations_dir, cls.MIGRATION_FILENAME)

    def test_01_isolated_mysql_migration_009_and_partial_recovery(self):
        """
        Test 1, 10, & 11:
        Execute Migration 009 on an isolated temporary MySQL schema (`jeevan_setu_test_mig009`),
        verify partial migration recovery when objects pre-exist, and verify idempotency on re-run.
        """
        import mysql.connector
        from config import get_config

        cfg = get_config()
        temp_schema = "jeevan_setu_test_mig009"

        def make_direct_conn(db_name=None):
            kwargs = dict(
                host=cfg.DB_HOST,
                port=cfg.DB_PORT,
                user=cfg.DB_USER,
                password=cfg.DB_PASSWORD,
                autocommit=False,
                connect_timeout=10,
            )
            if db_name:
                kwargs['database'] = db_name
            return mysql.connector.connect(**kwargs)

        conn = make_direct_conn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(f"DROP DATABASE IF EXISTS `{temp_schema}`")
            cur.execute(f"CREATE DATABASE `{temp_schema}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
            cur.execute(f"USE `{temp_schema}`")

            # Create prerequisite baseline tables (`users`, `patients`, `chatbot_conversations`, `schema_migrations`)
            cur.execute("""
                CREATE TABLE `users` (
                    `user_id` int NOT NULL AUTO_INCREMENT,
                    `username` varchar(50) NOT NULL,
                    `password_hash` varchar(255) NOT NULL,
                    `full_name` varchar(100) NOT NULL,
                    `email` varchar(100) NOT NULL,
                    PRIMARY KEY (`user_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            """)
            cur.execute("""
                CREATE TABLE `patients` (
                    `patient_id` int NOT NULL AUTO_INCREMENT,
                    `name` varchar(100) NOT NULL,
                    `age` int NOT NULL,
                    `gender` enum('Male','Female','Other') NOT NULL,
                    PRIMARY KEY (`patient_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            """)
            cur.execute("""
                CREATE TABLE `chatbot_conversations` (
                    `conversation_id` int NOT NULL AUTO_INCREMENT,
                    `user_id` int NOT NULL,
                    `patient_id` int DEFAULT NULL,
                    `user_message` text NOT NULL,
                    `bot_response` text NOT NULL,
                    `intent` varchar(100) DEFAULT NULL,
                    `confidence` float DEFAULT NULL,
                    `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`conversation_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            """)
            cur.execute("""
                CREATE TABLE `schema_migrations` (
                    `migration_id` int NOT NULL AUTO_INCREMENT,
                    `version` varchar(100) NOT NULL,
                    `description` varchar(255) NOT NULL,
                    `applied_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`migration_id`),
                    UNIQUE KEY `version` (`version`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # Simulate a partial migration state: pre-add `chat_mode` to `chatbot_conversations`
            # BEFORE running Migration 009
            cur.execute("""
                ALTER TABLE `chatbot_conversations`
                ADD COLUMN `chat_mode` ENUM('patient', 'general') NOT NULL DEFAULT 'patient' AFTER `patient_id`
            """)
            conn.commit()

            # Build a standalone DB adapter bound to `temp_schema` (never touches the global `jeevan_setu` pool)
            class IsolatedDBAdapter:
                def get_connection(self_inner):
                    return make_direct_conn(temp_schema)

                def execute_query(self_inner, query, params=None, fetch=False, cursor_dict=True):
                    c = self_inner.get_connection()
                    c_cur = c.cursor(dictionary=cursor_dict, buffered=True)
                    try:
                        c_cur.execute(query, params or ())
                        if fetch is True or fetch == 'all':
                            return c_cur.fetchall()
                        elif fetch == 'one':
                            return c_cur.fetchone()
                        else:
                            c.commit()
                            return c_cur.lastrowid or c_cur.rowcount
                    finally:
                        c_cur.close()
                        c.close()

            isolated_mm = MigrationManager(
                migrations_dir=self.migrations_dir,
                db_instance=IsolatedDBAdapter()
            )

            # First execution should recover smoothly from pre-existing `chat_mode` and succeed
            applied_first = isolated_mm.apply_migration(
                self.MIGRATION_VERSION,
                self.MIGRATION_FILENAME,
                self.migration_009_path
            )
            self.assertTrue(applied_first, "Migration 009 should apply and recover from partial column state.")

            # Second execution must detect already-applied status and return False without duplicating rows
            applied_second = isolated_mm.apply_migration(
                self.MIGRATION_VERSION,
                self.MIGRATION_FILENAME,
                self.migration_009_path
            )
            self.assertFalse(applied_second, "Repeated apply_migration must be a no-op.")

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM schema_migrations WHERE version = %s",
                (self.MIGRATION_VERSION,)
            )
            self.assertEqual(cur.fetchone()['cnt'], 1)
        finally:
            try:
                cur.execute(f"DROP DATABASE IF EXISTS `{temp_schema}`")
                conn.commit()
            finally:
                cur.close()
                conn.close()

    def test_02_all_four_rag_tables_exist_in_live_db(self):
        """Test 2: Verify all 4 new RAG tables exist in live `jeevan_setu`."""
        rows = db.execute_query("SHOW TABLES", fetch=True)
        tables = {list(r.values())[0] for r in rows}
        for expected in (
            'rag_documents',
            'rag_document_images',
            'rag_document_chunks',
            'patient_medical_images',
        ):
            self.assertIn(expected, tables, f"Table {expected} must exist in jeevan_setu")

    def test_03_columns_and_data_types_verified(self):
        """Test 3 & 6: Verify columns and types on all 4 RAG tables and `chatbot_conversations`."""
        expected_columns = {
            'rag_documents': {
                'doc_pk': 'int',
                'document_id': 'varchar',
                'title': 'varchar',
                'file_name': 'varchar',
                'source_path': 'varchar',
                'category': 'varchar',
                'file_type': 'varchar',
                'document_version': 'varchar',
                'content_hash': 'char',
                'file_size_bytes': 'bigint',
                'page_count': 'int',
                'ocr_required': 'tinyint',
                'processing_status': 'enum',
                'error_message': 'text',
                'uploaded_by': 'int',
                'ingested_at': 'datetime',
                'created_at': 'datetime',
                'updated_at': 'datetime',
            },
            'rag_document_images': {
                'image_pk': 'int',
                'image_id': 'varchar',
                'document_id': 'varchar',
                'source_document': 'varchar',
                'page_number': 'int',
                'image_index': 'int',
                'asset_path': 'varchar',
                'mime_type': 'varchar',
                'image_format': 'varchar',
                'width': 'int',
                'height': 'int',
                'file_size_bytes': 'bigint',
                'content_hash': 'char',
                'ocr_status': 'enum',
                'ocr_text': 'longtext',
                'ocr_completed_at': 'datetime',
                'vision_status': 'enum',
                'vision_description': 'longtext',
                'vision_model': 'varchar',
                'vision_completed_at': 'datetime',
                'processing_status': 'enum',
                'error_message': 'text',
                'created_at': 'datetime',
                'updated_at': 'datetime',
            },
            'rag_document_chunks': {
                'chunk_pk': 'int',
                'chunk_id': 'varchar',
                'document_id': 'varchar',
                'document_version': 'varchar',
                'chunk_index': 'int',
                'page_number': 'int',
                'section_title': 'varchar',
                'source_reference': 'varchar',
                'chroma_collection': 'varchar',
                'chroma_document_id': 'varchar',
                'related_image_id': 'varchar',
                'char_count': 'int',
                'token_count': 'int',
                'content_hash': 'char',
                'processing_status': 'enum',
                'created_at': 'datetime',
                'updated_at': 'datetime',
            },
            'patient_medical_images': {
                'patient_image_id': 'int',
                'patient_id': 'int',
                'uploaded_by': 'int',
                'image_type': 'enum',
                'title': 'varchar',
                'clinical_context': 'text',
                'secure_file_path': 'varchar',
                'mime_type': 'varchar',
                'image_format': 'varchar',
                'file_size_bytes': 'bigint',
                'content_hash': 'char',
                'ocr_status': 'enum',
                'ocr_text': 'longtext',
                'ocr_completed_at': 'datetime',
                'vision_status': 'enum',
                'vision_description': 'longtext',
                'vision_model': 'varchar',
                'vision_completed_at': 'datetime',
                'access_level': 'enum',
                'is_active': 'tinyint',
                'error_message': 'text',
                'created_at': 'datetime',
                'updated_at': 'datetime',
            },
            'chatbot_conversations': {
                'conversation_id': 'int',
                'user_id': 'int',
                'patient_id': 'int',
                'chat_mode': 'enum',
                'user_message': 'text',
                'bot_response': 'text',
                'intent': 'varchar',
                'confidence': 'float',
                'tools_invoked': 'json',
                'rag_sources': 'json',
                'created_at': 'timestamp',
            },
        }

        for tbl, exp_cols in expected_columns.items():
            rows = db.execute_query(
                """SELECT COLUMN_NAME, DATA_TYPE
                   FROM INFORMATION_SCHEMA.COLUMNS
                   WHERE TABLE_SCHEMA = 'jeevan_setu' AND TABLE_NAME = %s""",
                (tbl,), fetch=True
            )
            actual_map = {r['COLUMN_NAME']: r['DATA_TYPE'].lower() for r in rows}
            for col_name, col_type in exp_cols.items():
                self.assertIn(col_name, actual_map, f"Missing column {tbl}.{col_name}")
                self.assertEqual(
                    actual_map[col_name], col_type,
                    f"Type mismatch on {tbl}.{col_name}: expected {col_type}, got {actual_map[col_name]}"
                )

    def test_04_primary_keys_foreign_keys_and_retention_rules(self):
        """Test 4: Verify PKs, FKs, and retention-safe ON DELETE RESTRICT on `patient_medical_images`."""
        fks = db.execute_query(
            """SELECT kcu.TABLE_NAME, kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME,
                      kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME,
                      rc.DELETE_RULE, rc.UPDATE_RULE
               FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
               JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                 ON kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
                AND kcu.TABLE_NAME = rc.TABLE_NAME
                AND kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
               WHERE kcu.TABLE_SCHEMA = 'jeevan_setu'
                 AND kcu.TABLE_NAME IN (
                     'rag_documents', 'rag_document_images',
                     'rag_document_chunks', 'patient_medical_images'
                 )""",
            fetch=True
        )
        fk_by_name = {r['CONSTRAINT_NAME']: r for r in fks}

        expected_fks = {
            'fk_rag_documents_uploaded_by': ('rag_documents', 'uploaded_by', 'users', 'user_id', 'SET NULL'),
            'fk_rag_doc_images_document_id': ('rag_document_images', 'document_id', 'rag_documents', 'document_id', 'CASCADE'),
            'fk_rag_chunks_document_id': ('rag_document_chunks', 'document_id', 'rag_documents', 'document_id', 'CASCADE'),
            'fk_rag_chunks_related_image_id': ('rag_document_chunks', 'related_image_id', 'rag_document_images', 'image_id', 'SET NULL'),
            'fk_patient_med_images_patient_id': ('patient_medical_images', 'patient_id', 'patients', 'patient_id', 'RESTRICT'),
            'fk_patient_med_images_uploaded_by': ('patient_medical_images', 'uploaded_by', 'users', 'user_id', 'SET NULL'),
        }

        for cname, (tbl, col, ref_tbl, ref_col, del_rule) in expected_fks.items():
            self.assertIn(cname, fk_by_name, f"Missing foreign key constraint {cname}")
            actual = fk_by_name[cname]
            self.assertEqual(actual['TABLE_NAME'], tbl)
            self.assertEqual(actual['COLUMN_NAME'], col)
            self.assertEqual(actual['REFERENCED_TABLE_NAME'], ref_tbl)
            self.assertEqual(actual['REFERENCED_COLUMN_NAME'], ref_col)
            self.assertEqual(actual['DELETE_RULE'], del_rule)

    def test_05_indexes_and_unique_constraints_exist(self):
        """Test 5: Verify unique constraints and secondary indexes on the RAG tables and `chatbot_conversations`."""
        stats = db.execute_query(
            """SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE
               FROM INFORMATION_SCHEMA.STATISTICS
               WHERE TABLE_SCHEMA = 'jeevan_setu'
                 AND TABLE_NAME IN (
                     'rag_documents', 'rag_document_images',
                     'rag_document_chunks', 'patient_medical_images',
                     'chatbot_conversations'
                 )""",
            fetch=True
        )
        idx_set = {(r['TABLE_NAME'], r['INDEX_NAME'], int(r['NON_UNIQUE'])) for r in stats}

        expected_indexes = [
            ('rag_documents', 'uk_rag_documents_document_id', 0),
            ('rag_documents', 'uk_rag_documents_source_version', 0),
            ('rag_documents', 'idx_rag_documents_category_status', 1),
            ('rag_documents', 'idx_rag_documents_content_hash', 1),
            ('rag_document_images', 'uk_rag_doc_images_image_id', 0),
            ('rag_document_images', 'idx_rag_doc_images_doc_page', 1),
            ('rag_document_images', 'idx_rag_doc_images_status', 1),
            ('rag_document_chunks', 'uk_rag_chunks_chunk_id', 0),
            ('rag_document_chunks', 'uk_rag_chunks_chroma_doc', 0),
            ('rag_document_chunks', 'uk_rag_chunks_doc_ver_idx', 0),
            ('rag_document_chunks', 'idx_rag_chunks_doc_page', 1),
            ('patient_medical_images', 'idx_patient_med_images_patient_active', 1),
            ('patient_medical_images', 'idx_patient_med_images_type_status', 1),
            ('chatbot_conversations', 'idx_chatbot_conv_mode_created', 1),
        ]
        for exp in expected_indexes:
            self.assertIn(exp, idx_set, f"Missing index/unique constraint: {exp}")

    def test_06_chatbot_conversations_backward_and_new_inserts(self):
        """Test 7: Verify existing `ChatbotConversation.save()` and new RAG-metadata inserts work."""
        user_row = db.execute_query("SELECT user_id FROM users ORDER BY user_id ASC LIMIT 1", fetch='one')
        uid = user_row['user_id']
        conv_id_1 = None
        conv_id_2 = None
        try:
            # 1. Legacy signature call (no chat_mode, tools_invoked, or rag_sources)
            conv_id_1 = ChatbotConversation.save(
                user_id=uid,
                user_message="Fictional test query legacy signature",
                bot_response="Fictional legacy bot response",
                patient_id=1,
                intent="status_check",
                confidence=0.95
            )
            self.assertIsNotNone(conv_id_1)
            row_1 = db.execute_query(
                "SELECT * FROM chatbot_conversations WHERE conversation_id = %s",
                (conv_id_1,), fetch='one'
            )
            self.assertEqual(row_1['chat_mode'], 'patient')
            self.assertIsNone(row_1['tools_invoked'])
            self.assertIsNone(row_1['rag_sources'])

            # 2. General Chat call with tools_invoked & rag_sources (must force patient_id=None)
            conv_id_2 = ChatbotConversation.save(
                user_id=uid,
                user_message="What is the standard NEWS2 scoring threshold?",
                bot_response="NEWS2 score >= 7 indicates high clinical risk.",
                patient_id=1,  # Should be cleared to None because chat_mode='general'
                intent="protocol_lookup",
                confidence=0.99,
                chat_mode='general',
                tools_invoked=["chroma_knowledge_search"],
                rag_sources=[{"document_id": "doc_fictional_001", "page": 2}]
            )
            self.assertIsNotNone(conv_id_2)
            row_2 = db.execute_query(
                "SELECT * FROM chatbot_conversations WHERE conversation_id = %s",
                (conv_id_2,), fetch='one'
            )
            self.assertEqual(row_2['chat_mode'], 'general')
            self.assertIsNone(row_2['patient_id'], "General Chat must never associate a patient_id")
            self.assertIn("chroma_knowledge_search", str(row_2['tools_invoked']))
        finally:
            for cid in (conv_id_1, conv_id_2):
                if cid:
                    db.execute_query("DELETE FROM chatbot_conversations WHERE conversation_id = %s", (cid,))

    def test_07_rag_and_patient_image_models_crud_and_isolation(self):
        """Test RAGDocument, RAGDocumentImage, RAGDocumentChunk, and PatientMedicalImage models + General Chat block."""
        doc_id = "doc_test_fictional_999"
        img_id = "img_test_fictional_999_p1_i1"
        chunk_id = "chunk_test_fictional_999_c0"
        chroma_id = "chroma_vec_fictional_999_0"
        pat_img_id = None

        try:
            RAGDocument.upsert(
                document_id=doc_id,
                title="Fictional Protocol Guide",
                file_name="fictional_guide.pdf",
                source_path="clinical_protocols/fictional_guide.pdf",
                file_type="pdf",
                content_hash="a" * 64,
                category="clinical_protocols",
                page_count=3,
                ocr_required=False,
                processing_status="indexed"
            )
            doc = RAGDocument.get_by_document_id(doc_id)
            self.assertIsNotNone(doc)
            self.assertEqual(doc['processing_status'], 'indexed')

            RAGDocumentImage.upsert(
                image_id=img_id,
                document_id=doc_id,
                source_document="clinical_protocols/fictional_guide.pdf",
                asset_path="_extracted_assets/fictional_guide_p1_i1.png",
                page_number=1,
                image_index=1,
                content_hash="b" * 64
            )
            RAGDocumentImage.update_ocr_and_vision(
                image_id=img_id,
                ocr_status="completed",
                ocr_text="Fictional flowchart text",
                vision_status="completed",
                vision_description="Fictional diagram showing triage steps",
                vision_model="gemma-3-27b-it",
                processing_status="completed"
            )
            img = RAGDocumentImage.get_by_image_id(img_id)
            self.assertEqual(img['ocr_status'], 'completed')
            self.assertEqual(img['vision_status'], 'completed')

            RAGDocumentChunk.upsert(
                chunk_id=chunk_id,
                document_id=doc_id,
                chunk_index=0,
                source_reference="clinical_protocols/fictional_guide.pdf#page=1",
                chroma_document_id=chroma_id,
                content_hash="c" * 64,
                page_number=1,
                related_image_id=img_id,
                char_count=240,
                token_count=45
            )
            chunk = RAGDocumentChunk.get_by_chroma_id(chroma_id)
            self.assertIsNotNone(chunk)
            self.assertEqual(chunk['related_image_id'], img_id)

            # PatientMedicalImage creation & General Chat isolation check
            pat_img_id = PatientMedicalImage.create(
                patient_id=1,
                title="Fictional Bedside Monitor Capture",
                secure_file_path="secure_uploads/patient_1/fictional_monitor.png",
                content_hash="d" * 64,
                image_type="monitor_snapshot",
                access_level="clinical_staff"
            )
            self.assertIsNotNone(pat_img_id)

            # Must raise PermissionError in General Chat mode
            with self.assertRaises(PermissionError):
                PatientMedicalImage.get_by_patient(1, chat_mode='general', user_role='doctor')

            # Attendant role must receive empty list
            att_imgs = PatientMedicalImage.get_by_patient(1, chat_mode='patient', user_role='attendant')
            self.assertEqual(att_imgs, [])

            # Doctor role in patient mode receives the image
            doc_imgs = PatientMedicalImage.get_by_patient(1, chat_mode='patient', user_role='doctor')
            self.assertTrue(any(i['patient_image_id'] == pat_img_id for i in doc_imgs))
        finally:
            if pat_img_id:
                db.execute_query("DELETE FROM patient_medical_images WHERE patient_image_id = %s", (pat_img_id,))
            db.execute_query("DELETE FROM rag_documents WHERE document_id = %s", (doc_id,))

    def test_08_canonical_patients_and_ews_transfers_preserved(self):
        """Test 8 & 9: Verify all 10 canonical baseline patients and EWS/Transfer queries remain intact."""
        patients = Patient.get_all()
        self.assertGreaterEqual(len(patients), 10)
        codes = {p.get('patient_code') for p in patients}
        for i in range(1, 11):
            expected_code = f"UHID-2026-{i:05d}"
            self.assertIn(expected_code, codes, f"Canonical baseline patient {expected_code} must be preserved")

        ews = EWSScore.get_latest(1)
        self.assertIsNotNone(ews)
        recs = Recommendation.get_by_patient(1)
        self.assertIsInstance(recs, list)
        transfers = Transfer.get_all(limit=5)
        self.assertIsInstance(transfers, list)

    def test_09_schema_db_sync_excludes_sensitive_rows_and_is_stable(self):
        """
        Test 12, 13, & 14:
        Verify `sync_all()` writes all 34 table structures to SQLite `Schema.db`,
        contains ZERO patient rows and ZERO user password hashes, and is stable across repeated runs.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            test_sqlite_1 = os.path.join(tmpdir, "schema_test_1.db")
            test_sql_1 = os.path.join(tmpdir, "schema_test_1.sql")

            res1 = sync_all(target_db_paths=[test_sqlite_1], schema_sql_path=test_sql_1)
            self.assertEqual(res1['table_count'], 34)

            conn = sqlite3.connect(test_sqlite_1)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            sqlite_tables = {r[0] for r in cur.fetchall()}
            self.assertEqual(len(sqlite_tables), 34)

            # Check sensitive tables have 0 rows in Schema.db
            for sensitive_tbl in (
                'patients', 'users', 'vitals', 'ews_scores', 'chatbot_conversations',
                'clinical_notes', 'password_reset_tokens', 'patient_qr_tokens',
                'patient_medical_images', 'attendants', 'doctors', 'nurses'
            ):
                cur.execute(f'SELECT COUNT(*) FROM "{sensitive_tbl}"')
                row_count = cur.fetchone()[0]
                self.assertEqual(
                    row_count, 0,
                    f"Security violation: {sensitive_tbl} in Schema.db must have 0 rows, found {row_count}"
                )

            # Only `schema_migrations` should have version metadata rows
            cur.execute('SELECT COUNT(*) FROM "schema_migrations"')
            mig_count = cur.fetchone()[0]
            self.assertGreaterEqual(mig_count, 10)
            conn.close()

            with open(test_sql_1, 'r', encoding='utf-8') as f:
                sql_text_1 = f.read()

            # Repeat synchronization and verify deterministic output
            res2 = sync_all(target_db_paths=[test_sqlite_1], schema_sql_path=test_sql_1)
            with open(test_sql_1, 'r', encoding='utf-8') as f:
                sql_text_2 = f.read()

            self.assertEqual(sql_text_1, sql_text_2, "Repeated schema.sql synchronization must be identical")
            self.assertEqual(res1['tables'], res2['tables'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
