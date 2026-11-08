-- ============================================================================
-- Migration 009: Agentic Hybrid RAG & Multimodal RAG Metadata Tables
-- Target Database: jeevan_setu (MySQL 8.0+ / InnoDB / utf8mb4)
-- Version: 009_agentic_hybrid_multimodal_rag
-- Description:
--   1. Creates rag_documents (approved knowledge-base document registry)
--   2. Creates rag_document_images (extracted PDF/DOCX images + OCR/Vision metadata)
--   3. Creates rag_document_chunks (chunk metadata mapped to ChromaDB vector IDs)
--   4. Creates patient_medical_images (patient-specific medical image metadata,
--      strictly isolated from shared ChromaDB, with retention-safe ON DELETE RESTRICT)
--   5. Extends chatbot_conversations with backward-compatible chat_mode,
--      tools_invoked, and rag_sources columns + idx_chatbot_conv_mode_created index
-- ============================================================================

-- 1. Knowledge-Base Document Registry
CREATE TABLE IF NOT EXISTS `rag_documents` (
    `doc_pk` INT NOT NULL AUTO_INCREMENT,
    `document_id` VARCHAR(64) NOT NULL,
    `title` VARCHAR(255) NOT NULL,
    `file_name` VARCHAR(255) NOT NULL,
    `source_path` VARCHAR(512) NOT NULL,
    `category` VARCHAR(100) NOT NULL DEFAULT 'general',
    `file_type` VARCHAR(32) NOT NULL,
    `document_version` VARCHAR(32) NOT NULL DEFAULT '1.0',
    `content_hash` CHAR(64) NOT NULL,
    `file_size_bytes` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `page_count` INT UNSIGNED NOT NULL DEFAULT 1,
    `ocr_required` TINYINT(1) NOT NULL DEFAULT 0,
    `processing_status` ENUM('pending', 'processing', 'indexed', 'failed', 'archived') NOT NULL DEFAULT 'pending',
    `error_message` TEXT NULL,
    `uploaded_by` INT NULL,
    `ingested_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`doc_pk`),
    UNIQUE KEY `uk_rag_documents_document_id` (`document_id`),
    UNIQUE KEY `uk_rag_documents_source_version` (`source_path`, `document_version`),
    KEY `idx_rag_documents_category_status` (`category`, `processing_status`),
    KEY `idx_rag_documents_content_hash` (`content_hash`),
    KEY `idx_rag_documents_uploaded_by` (`uploaded_by`),
    CONSTRAINT `fk_rag_documents_uploaded_by`
        FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`user_id`)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Extracted Knowledge-Document Images & OCR/Vision Metadata
CREATE TABLE IF NOT EXISTS `rag_document_images` (
    `image_pk` INT NOT NULL AUTO_INCREMENT,
    `image_id` VARCHAR(64) NOT NULL,
    `document_id` VARCHAR(64) NOT NULL,
    `source_document` VARCHAR(512) NOT NULL,
    `page_number` INT UNSIGNED NULL,
    `image_index` INT UNSIGNED NOT NULL DEFAULT 1,
    `asset_path` VARCHAR(512) NOT NULL,
    `mime_type` VARCHAR(64) NOT NULL DEFAULT 'image/png',
    `image_format` VARCHAR(16) NOT NULL DEFAULT 'png',
    `width` INT UNSIGNED NULL,
    `height` INT UNSIGNED NULL,
    `file_size_bytes` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `content_hash` CHAR(64) NULL,
    `ocr_status` ENUM('not_required', 'pending', 'processing', 'completed', 'failed') NOT NULL DEFAULT 'pending',
    `ocr_text` LONGTEXT NULL,
    `ocr_completed_at` DATETIME NULL,
    `vision_status` ENUM('not_required', 'pending', 'processing', 'completed', 'failed') NOT NULL DEFAULT 'pending',
    `vision_description` LONGTEXT NULL,
    `vision_model` VARCHAR(128) NULL,
    `vision_completed_at` DATETIME NULL,
    `processing_status` ENUM('pending', 'processing', 'completed', 'failed') NOT NULL DEFAULT 'pending',
    `error_message` TEXT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`image_pk`),
    UNIQUE KEY `uk_rag_doc_images_image_id` (`image_id`),
    KEY `idx_rag_doc_images_doc_page` (`document_id`, `page_number`),
    KEY `idx_rag_doc_images_status` (`processing_status`, `ocr_status`, `vision_status`),
    CONSTRAINT `fk_rag_doc_images_document_id`
        FOREIGN KEY (`document_id`) REFERENCES `rag_documents` (`document_id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. RAG Document Chunks & ChromaDB Vector Reference Mapping
CREATE TABLE IF NOT EXISTS `rag_document_chunks` (
    `chunk_pk` INT NOT NULL AUTO_INCREMENT,
    `chunk_id` VARCHAR(96) NOT NULL,
    `document_id` VARCHAR(64) NOT NULL,
    `document_version` VARCHAR(32) NOT NULL DEFAULT '1.0',
    `chunk_index` INT UNSIGNED NOT NULL,
    `page_number` INT UNSIGNED NULL,
    `section_title` VARCHAR(255) NULL,
    `source_reference` VARCHAR(512) NOT NULL,
    `chroma_collection` VARCHAR(128) NOT NULL DEFAULT 'jeevan_setu_knowledge',
    `chroma_document_id` VARCHAR(128) NOT NULL,
    `related_image_id` VARCHAR(64) NULL,
    `char_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `token_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `content_hash` CHAR(64) NOT NULL,
    `processing_status` ENUM('pending', 'indexed', 'failed', 'deleted') NOT NULL DEFAULT 'indexed',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`chunk_pk`),
    UNIQUE KEY `uk_rag_chunks_chunk_id` (`chunk_id`),
    UNIQUE KEY `uk_rag_chunks_chroma_doc` (`chroma_collection`, `chroma_document_id`),
    UNIQUE KEY `uk_rag_chunks_doc_ver_idx` (`document_id`, `document_version`, `chunk_index`),
    KEY `idx_rag_chunks_doc_page` (`document_id`, `page_number`),
    KEY `idx_rag_chunks_related_image` (`related_image_id`),
    KEY `idx_rag_chunks_status` (`processing_status`),
    CONSTRAINT `fk_rag_chunks_document_id`
        FOREIGN KEY (`document_id`) REFERENCES `rag_documents` (`document_id`)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_rag_chunks_related_image_id`
        FOREIGN KEY (`related_image_id`) REFERENCES `rag_document_images` (`image_id`)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Patient-Specific Medical Images (Strictly Isolated from Shared ChromaDB)
-- Retention-safe design: fk_patient_med_images_patient_id uses ON DELETE RESTRICT
-- so clinical image metadata cannot be accidentally wiped out by a hard DELETE on patients.
CREATE TABLE IF NOT EXISTS `patient_medical_images` (
    `patient_image_id` INT NOT NULL AUTO_INCREMENT,
    `patient_id` INT NOT NULL,
    `uploaded_by` INT NULL,
    `image_type` ENUM('ecg', 'xray', 'ct_scan', 'lab_report', 'monitor_snapshot', 'clinical_chart', 'other') NOT NULL DEFAULT 'other',
    `title` VARCHAR(255) NOT NULL,
    `clinical_context` TEXT NULL,
    `secure_file_path` VARCHAR(512) NOT NULL,
    `mime_type` VARCHAR(64) NOT NULL DEFAULT 'image/png',
    `image_format` VARCHAR(16) NOT NULL DEFAULT 'png',
    `file_size_bytes` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    `content_hash` CHAR(64) NOT NULL,
    `ocr_status` ENUM('not_required', 'pending', 'processing', 'completed', 'failed') NOT NULL DEFAULT 'pending',
    `ocr_text` LONGTEXT NULL,
    `ocr_completed_at` DATETIME NULL,
    `vision_status` ENUM('not_required', 'pending', 'processing', 'completed', 'failed') NOT NULL DEFAULT 'pending',
    `vision_description` LONGTEXT NULL,
    `vision_model` VARCHAR(128) NULL,
    `vision_completed_at` DATETIME NULL,
    `access_level` ENUM('clinical_staff', 'doctor_only', 'admin_only') NOT NULL DEFAULT 'clinical_staff',
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `error_message` TEXT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`patient_image_id`),
    KEY `idx_patient_med_images_patient_active` (`patient_id`, `is_active`, `created_at`),
    KEY `idx_patient_med_images_uploaded_by` (`uploaded_by`),
    KEY `idx_patient_med_images_type_status` (`image_type`, `ocr_status`, `vision_status`),
    KEY `idx_patient_med_images_hash` (`content_hash`),
    CONSTRAINT `fk_patient_med_images_patient_id`
        FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `fk_patient_med_images_uploaded_by`
        FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`user_id`)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Backward-Compatible Extension to chatbot_conversations
-- Separate ALTER statements so partial recovery can skip already-applied columns/indexes cleanly
ALTER TABLE `chatbot_conversations`
    ADD COLUMN `chat_mode` ENUM('patient', 'general') NOT NULL DEFAULT 'patient' AFTER `patient_id`;

ALTER TABLE `chatbot_conversations`
    ADD COLUMN `tools_invoked` JSON NULL AFTER `confidence`;

ALTER TABLE `chatbot_conversations`
    ADD COLUMN `rag_sources` JSON NULL AFTER `tools_invoked`;

ALTER TABLE `chatbot_conversations`
    ADD INDEX `idx_chatbot_conv_mode_created` (`chat_mode`, `created_at`);

