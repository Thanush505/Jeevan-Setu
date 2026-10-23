-- Migration: 007_create_attendant_assistance_requests.sql
-- Description: Create attendant_assistance_requests table for Attendant Portal Request Assistance feature

CREATE TABLE IF NOT EXISTS attendant_assistance_requests (
    request_id          INT AUTO_INCREMENT PRIMARY KEY,
    patient_id          INT NOT NULL,
    attendant_name      VARCHAR(100) NOT NULL,
    attendant_id        INT DEFAULT NULL,
    category            VARCHAR(100) NOT NULL,
    description         TEXT DEFAULT NULL,
    status              ENUM('submitted', 'pending', 'acknowledged', 'in_progress', 'resolved', 'cancelled', 'rejected') NOT NULL DEFAULT 'pending',
    assigned_ward_id    INT DEFAULT NULL,
    assigned_nurse_id   INT DEFAULT NULL,
    assigned_user_id    INT DEFAULT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at     TIMESTAMP NULL DEFAULT NULL,
    started_at          TIMESTAMP NULL DEFAULT NULL,
    resolved_at         TIMESTAMP NULL DEFAULT NULL,
    cancelled_at        TIMESTAMP NULL DEFAULT NULL,
    rejected_at         TIMESTAMP NULL DEFAULT NULL,
    closed_by_user_id   INT DEFAULT NULL,
    resolution_note     TEXT DEFAULT NULL,
    rejection_reason    TEXT DEFAULT NULL,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_aar_patient (patient_id),
    INDEX idx_aar_status (status),
    INDEX idx_aar_category (category),
    INDEX idx_aar_created_at (created_at),
    CONSTRAINT fk_aar_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    CONSTRAINT fk_aar_closed_by FOREIGN KEY (closed_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    CONSTRAINT fk_aar_assigned_user FOREIGN KEY (assigned_user_id) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
