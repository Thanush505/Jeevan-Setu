"""
models/chatbot_model.py — Model for chatbot conversation history and Agentic Hybrid Multimodal RAG metadata.
"""

import json

try:
    from database.db import db
except ImportError:
    class MockDB:
        def execute_query(self, *args, **kwargs):
            return []
    db = MockDB()


def _serialize_json_field(value):
    """Serialize list/dict metadata to JSON string or pass through None/str safely."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)


class ChatbotConversation:
    """Model for storing chatbot interactions with optional RAG & tool audit metadata."""

    VALID_CHAT_MODES = ('patient', 'general')

    @staticmethod
    def save(user_id, user_message, bot_response, patient_id=None,
             intent=None, confidence=None, chat_mode='patient',
             tools_invoked=None, rag_sources=None):
        """
        Save a chatbot conversation turn.
        Backward-compatible: existing callers passing only (user_id, user_message, bot_response,
        patient_id, intent, confidence) work without changes.
        Enforces General Chat isolation: if chat_mode == 'general', patient_id is forced to None.
        """
        mode = str(chat_mode or 'patient').lower()
        if mode not in ChatbotConversation.VALID_CHAT_MODES:
            mode = 'patient'
        if mode == 'general':
            patient_id = None

        tools_json = _serialize_json_field(tools_invoked)
        sources_json = _serialize_json_field(rag_sources)

        return db.execute_query(
            """INSERT INTO chatbot_conversations
               (user_id, patient_id, chat_mode, user_message, bot_response,
                intent, confidence, tools_invoked, rag_sources)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, patient_id, mode, user_message, bot_response,
             intent, confidence, tools_json, sources_json)
        )

    @staticmethod
    def get_history(user_id, limit=20, chat_mode=None):
        """Get conversation history for a user, optionally filtered by chat_mode."""
        if chat_mode and str(chat_mode).lower() in ChatbotConversation.VALID_CHAT_MODES:
            return db.execute_query(
                """SELECT * FROM chatbot_conversations
                   WHERE user_id = %s AND chat_mode = %s
                   ORDER BY created_at DESC LIMIT %s""",
                (user_id, str(chat_mode).lower(), limit), fetch=True
            )
        return db.execute_query(
            """SELECT * FROM chatbot_conversations WHERE user_id = %s
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, limit), fetch=True
        )

    @staticmethod
    def get_by_patient(patient_id, limit=20):
        """Get conversations related to a specific patient."""
        return db.execute_query(
            """SELECT * FROM chatbot_conversations WHERE patient_id = %s
               ORDER BY created_at DESC LIMIT %s""",
            (patient_id, limit), fetch=True
        )


class RAGDocument:
    """Model for approved knowledge-base document metadata (`rag_documents`)."""

    VALID_STATUSES = ('pending', 'processing', 'indexed', 'failed', 'archived')

    @staticmethod
    def upsert(document_id, title, file_name, source_path, file_type, content_hash,
               category='general', document_version='1.0', file_size_bytes=0,
               page_count=1, ocr_required=False, processing_status='pending',
               error_message=None, uploaded_by=None):
        """Insert or update a knowledge-base document metadata record."""
        status = processing_status if processing_status in RAGDocument.VALID_STATUSES else 'pending'
        return db.execute_query(
            """INSERT INTO rag_documents
               (document_id, title, file_name, source_path, category, file_type,
                document_version, content_hash, file_size_bytes, page_count,
                ocr_required, processing_status, error_message, uploaded_by,
                ingested_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       CASE WHEN %s = 'indexed' THEN CURRENT_TIMESTAMP ELSE NULL END)
               ON DUPLICATE KEY UPDATE
                   title = VALUES(title),
                   file_name = VALUES(file_name),
                   source_path = VALUES(source_path),
                   category = VALUES(category),
                   file_type = VALUES(file_type),
                   document_version = VALUES(document_version),
                   content_hash = VALUES(content_hash),
                   file_size_bytes = VALUES(file_size_bytes),
                   page_count = VALUES(page_count),
                   ocr_required = VALUES(ocr_required),
                   processing_status = VALUES(processing_status),
                   error_message = VALUES(error_message),
                   uploaded_by = COALESCE(VALUES(uploaded_by), uploaded_by),
                   ingested_at = CASE
                       WHEN VALUES(processing_status) = 'indexed' THEN CURRENT_TIMESTAMP
                       ELSE ingested_at
                   END""",
            (
                document_id, title, file_name, source_path, category, file_type,
                document_version, content_hash, int(file_size_bytes or 0),
                max(1, int(page_count or 1)), 1 if ocr_required else 0,
                status, error_message, uploaded_by, status
            )
        )

    @staticmethod
    def get_by_document_id(document_id):
        """Fetch a knowledge-base document record by its stable document_id."""
        return db.execute_query(
            "SELECT * FROM rag_documents WHERE document_id = %s",
            (document_id,), fetch='one'
        )

    @staticmethod
    def get_all(category=None, processing_status=None, limit=100):
        """List knowledge-base documents with optional category and status filters."""
        clauses = []
        params = []
        if category:
            clauses.append("category = %s")
            params.append(category)
        if processing_status:
            clauses.append("processing_status = %s")
            params.append(processing_status)
        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        return db.execute_query(
            f"SELECT * FROM rag_documents {where_sql} ORDER BY updated_at DESC LIMIT %s",
            tuple(params), fetch=True
        )

    @staticmethod
    def update_status(document_id, processing_status, error_message=None):
        """Update document processing status and optional error message."""
        return db.execute_query(
            """UPDATE rag_documents
               SET processing_status = %s,
                   error_message = %s,
                   ingested_at = CASE WHEN %s = 'indexed' THEN CURRENT_TIMESTAMP ELSE ingested_at END
               WHERE document_id = %s""",
            (processing_status, error_message, processing_status, document_id)
        )


class RAGDocumentImage:
    """Model for extracted knowledge-document images and OCR/Vision metadata (`rag_document_images`)."""

    @staticmethod
    def upsert(image_id, document_id, source_document, asset_path,
               page_number=None, image_index=1, mime_type='image/png',
               image_format='png', width=None, height=None, file_size_bytes=0,
               content_hash=None, ocr_status='pending', ocr_text=None,
               vision_status='pending', vision_description=None,
               vision_model=None, processing_status='pending', error_message=None):
        """Insert or update an extracted knowledge-document image record."""
        return db.execute_query(
            """INSERT INTO rag_document_images
               (image_id, document_id, source_document, page_number, image_index,
                asset_path, mime_type, image_format, width, height, file_size_bytes,
                content_hash, ocr_status, ocr_text, vision_status, vision_description,
                vision_model, processing_status, error_message)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                   asset_path = VALUES(asset_path),
                   mime_type = VALUES(mime_type),
                   image_format = VALUES(image_format),
                   width = COALESCE(VALUES(width), width),
                   height = COALESCE(VALUES(height), height),
                   file_size_bytes = VALUES(file_size_bytes),
                   content_hash = COALESCE(VALUES(content_hash), content_hash),
                   ocr_status = VALUES(ocr_status),
                   ocr_text = COALESCE(VALUES(ocr_text), ocr_text),
                   vision_status = VALUES(vision_status),
                   vision_description = COALESCE(VALUES(vision_description), vision_description),
                   vision_model = COALESCE(VALUES(vision_model), vision_model),
                   processing_status = VALUES(processing_status),
                   error_message = VALUES(error_message)""",
            (
                image_id, document_id, source_document, page_number, int(image_index or 1),
                asset_path, mime_type, image_format, width, height, int(file_size_bytes or 0),
                content_hash, ocr_status, ocr_text, vision_status, vision_description,
                vision_model, processing_status, error_message
            )
        )

    @staticmethod
    def get_by_image_id(image_id):
        """Fetch an extracted image record by image_id."""
        return db.execute_query(
            "SELECT * FROM rag_document_images WHERE image_id = %s",
            (image_id,), fetch='one'
        )

    @staticmethod
    def get_by_document(document_id):
        """Fetch all extracted images for a knowledge document ordered by page and index."""
        return db.execute_query(
            """SELECT * FROM rag_document_images
               WHERE document_id = %s
               ORDER BY COALESCE(page_number, 0) ASC, image_index ASC""",
            (document_id,), fetch=True
        )

    @staticmethod
    def update_ocr_and_vision(image_id, ocr_status=None, ocr_text=None,
                              vision_status=None, vision_description=None,
                              vision_model=None, processing_status=None,
                              error_message=None):
        """Update OCR and/or Vision processing outcomes for an extracted image."""
        return db.execute_query(
            """UPDATE rag_document_images
               SET ocr_status = COALESCE(%s, ocr_status),
                   ocr_text = COALESCE(%s, ocr_text),
                   ocr_completed_at = CASE WHEN %s = 'completed' THEN CURRENT_TIMESTAMP ELSE ocr_completed_at END,
                   vision_status = COALESCE(%s, vision_status),
                   vision_description = COALESCE(%s, vision_description),
                   vision_model = COALESCE(%s, vision_model),
                   vision_completed_at = CASE WHEN %s = 'completed' THEN CURRENT_TIMESTAMP ELSE vision_completed_at END,
                   processing_status = COALESCE(%s, processing_status),
                   error_message = %s
               WHERE image_id = %s""",
            (
                ocr_status, ocr_text, ocr_status,
                vision_status, vision_description, vision_model, vision_status,
                processing_status, error_message, image_id
            )
        )


class RAGDocumentChunk:
    """
    Model for mapping MySQL knowledge-document chunk metadata to ChromaDB vector IDs (`rag_document_chunks`).
    Never stores raw embedding arrays in MySQL.
    """

    @staticmethod
    def upsert(chunk_id, document_id, chunk_index, source_reference,
               chroma_document_id, content_hash, document_version='1.0',
               page_number=None, section_title=None,
               chroma_collection='jeevan_setu_knowledge', related_image_id=None,
               char_count=0, token_count=0, processing_status='indexed'):
        """Insert or update a chunk metadata reference mapped to ChromaDB."""
        return db.execute_query(
            """INSERT INTO rag_document_chunks
               (chunk_id, document_id, document_version, chunk_index, page_number,
                section_title, source_reference, chroma_collection, chroma_document_id,
                related_image_id, char_count, token_count, content_hash, processing_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                   page_number = VALUES(page_number),
                   section_title = VALUES(section_title),
                   source_reference = VALUES(source_reference),
                   chroma_collection = VALUES(chroma_collection),
                   chroma_document_id = VALUES(chroma_document_id),
                   related_image_id = VALUES(related_image_id),
                   char_count = VALUES(char_count),
                   token_count = VALUES(token_count),
                   content_hash = VALUES(content_hash),
                   processing_status = VALUES(processing_status)""",
            (
                chunk_id, document_id, document_version, int(chunk_index),
                page_number, section_title, source_reference, chroma_collection,
                chroma_document_id, related_image_id, int(char_count or 0),
                int(token_count or 0), content_hash, processing_status
            )
        )

    @staticmethod
    def get_by_document(document_id):
        """Fetch all chunk metadata records for a knowledge document."""
        return db.execute_query(
            """SELECT * FROM rag_document_chunks
               WHERE document_id = %s
               ORDER BY chunk_index ASC""",
            (document_id,), fetch=True
        )

    @staticmethod
    def get_by_chroma_id(chroma_document_id, chroma_collection='jeevan_setu_knowledge'):
        """Fetch a chunk metadata record by its ChromaDB document ID and collection."""
        return db.execute_query(
            """SELECT * FROM rag_document_chunks
               WHERE chroma_collection = %s AND chroma_document_id = %s""",
            (chroma_collection, chroma_document_id), fetch='one'
        )


class PatientMedicalImage:
    """
    Model for patient-specific medical image metadata (`patient_medical_images`).
    Strictly isolated from shared ChromaDB and prohibited in General Chat.
    """

    VALID_IMAGE_TYPES = (
        'ecg', 'xray', 'ct_scan', 'lab_report',
        'monitor_snapshot', 'clinical_chart', 'other'
    )
    VALID_ACCESS_LEVELS = ('clinical_staff', 'doctor_only', 'admin_only')

    @staticmethod
    def create(patient_id, title, secure_file_path, content_hash,
               uploaded_by=None, image_type='other', clinical_context=None,
               mime_type='image/png', image_format='png', file_size_bytes=0,
               ocr_status='pending', ocr_text=None, vision_status='pending',
               vision_description=None, vision_model=None,
               access_level='clinical_staff', is_active=True):
        """Create a patient-specific medical image metadata record."""
        img_type = image_type if image_type in PatientMedicalImage.VALID_IMAGE_TYPES else 'other'
        acc_level = access_level if access_level in PatientMedicalImage.VALID_ACCESS_LEVELS else 'clinical_staff'
        return db.execute_query(
            """INSERT INTO patient_medical_images
               (patient_id, uploaded_by, image_type, title, clinical_context,
                secure_file_path, mime_type, image_format, file_size_bytes,
                content_hash, ocr_status, ocr_text, vision_status,
                vision_description, vision_model, access_level, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                int(patient_id), uploaded_by, img_type, title, clinical_context,
                secure_file_path, mime_type, image_format, int(file_size_bytes or 0),
                content_hash, ocr_status, ocr_text, vision_status,
                vision_description, vision_model, acc_level, 1 if is_active else 0
            )
        )

    @staticmethod
    def get_by_id(patient_image_id):
        """Fetch a patient medical image record by its primary key."""
        return db.execute_query(
            "SELECT * FROM patient_medical_images WHERE patient_image_id = %s",
            (patient_image_id,), fetch='one'
        )

    @staticmethod
    def get_by_patient(patient_id, active_only=True, chat_mode='patient', user_role='doctor', limit=50):
        """
        Retrieve medical images for a specific patient.
        Enforces strict General Chat isolation and role-based access levels.
        """
        if str(chat_mode or '').lower() == 'general':
            raise PermissionError("Patient-specific medical images cannot be accessed in General Chat mode.")

        clauses = ["patient_id = %s"]
        params = [int(patient_id)]

        if active_only:
            clauses.append("is_active = 1")

        role = str(user_role or '').lower()
        if role == 'admin':
            pass
        elif role == 'doctor':
            clauses.append("access_level IN ('clinical_staff', 'doctor_only')")
        elif role in ('nurse', 'command_center'):
            clauses.append("access_level = 'clinical_staff'")
        else:
            # Attendants or unknown roles cannot access internal clinical medical images
            return []

        where_sql = " AND ".join(clauses)
        params.append(int(limit))
        return db.execute_query(
            f"""SELECT * FROM patient_medical_images
                WHERE {where_sql}
                ORDER BY created_at DESC LIMIT %s""",
            tuple(params), fetch=True
        )

    @staticmethod
    def update_analysis(patient_image_id, ocr_status=None, ocr_text=None,
                        vision_status=None, vision_description=None,
                        vision_model=None, error_message=None):
        """Update OCR and/or Vision analysis results for a patient medical image."""
        return db.execute_query(
            """UPDATE patient_medical_images
               SET ocr_status = COALESCE(%s, ocr_status),
                   ocr_text = COALESCE(%s, ocr_text),
                   ocr_completed_at = CASE WHEN %s = 'completed' THEN CURRENT_TIMESTAMP ELSE ocr_completed_at END,
                   vision_status = COALESCE(%s, vision_status),
                   vision_description = COALESCE(%s, vision_description),
                   vision_model = COALESCE(%s, vision_model),
                   vision_completed_at = CASE WHEN %s = 'completed' THEN CURRENT_TIMESTAMP ELSE vision_completed_at END,
                   error_message = %s
               WHERE patient_image_id = %s""",
            (
                ocr_status, ocr_text, ocr_status,
                vision_status, vision_description, vision_model, vision_status,
                error_message, int(patient_image_id)
            )
        )

    @staticmethod
    def deactivate(patient_image_id):
        """Soft-deactivate a patient medical image record without deleting clinical history."""
        return db.execute_query(
            "UPDATE patient_medical_images SET is_active = 0 WHERE patient_image_id = %s",
            (int(patient_image_id),)
        )
