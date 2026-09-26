-- Migration: 002_core_phase2_tables.sql
-- Description: Core tables for Phase 2: roles, wards, beds, bed_management, patient_qr_tokens, ews_scores, recommendations, transfers, notifications, audit_logs

SET FOREIGN_KEY_CHECKS = 0;

-- 1. Roles
CREATE TABLE IF NOT EXISTS roles (
    role_id         INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(50) UNIQUE NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    description     VARCHAR(255) NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Wards
CREATE TABLE IF NOT EXISTS wards (
    ward_id         INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) UNIQUE NOT NULL,
    ward_type       ENUM('ICU', 'HDU', 'General') NOT NULL DEFAULT 'ICU',
    floor_number    INT DEFAULT 1,
    total_beds      INT NOT NULL DEFAULT 10,
    description     VARCHAR(255) NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Beds
CREATE TABLE IF NOT EXISTS beds (
    bed_id          INT AUTO_INCREMENT PRIMARY KEY,
    ward_id         INT NOT NULL,
    bed_number      VARCHAR(20) NOT NULL,
    status          ENUM('available', 'occupied', 'maintenance', 'reserved') NOT NULL DEFAULT 'available',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ward_bed (ward_id, bed_number),
    FOREIGN KEY (ward_id) REFERENCES wards(ward_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Bed Management (Allocations)
CREATE TABLE IF NOT EXISTS bed_management (
    allocation_id   INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    bed_id          INT NOT NULL,
    ward_id         INT NOT NULL,
    allocated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    released_at     DATETIME NULL,
    status          ENUM('allocated', 'occupied', 'released', 'transferred') NOT NULL DEFAULT 'allocated',
    allocated_by    INT NULL,
    notes           TEXT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (bed_id) REFERENCES beds(bed_id) ON DELETE RESTRICT,
    FOREIGN KEY (ward_id) REFERENCES wards(ward_id) ON DELETE RESTRICT,
    FOREIGN KEY (allocated_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Patient QR Tokens
CREATE TABLE IF NOT EXISTS patient_qr_tokens (
    token_id        INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    token_hash      VARCHAR(255) UNIQUE NOT NULL,
    access_code     VARCHAR(50) NOT NULL,
    qr_code_data    TEXT NULL,
    valid_from      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      DATETIME NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_by      INT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. EWS Scores
CREATE TABLE IF NOT EXISTS ews_scores (
    ews_id              INT AUTO_INCREMENT PRIMARY KEY,
    patient_id          INT NOT NULL,
    vital_id            INT NOT NULL,
    total_score         INT NOT NULL DEFAULT 0,
    risk_level          ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL DEFAULT 'LOW',
    hr_score            INT DEFAULT 0,
    bp_score            INT DEFAULT 0,
    rr_score            INT DEFAULT 0,
    temp_score          INT DEFAULT 0,
    calculated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (vital_id) REFERENCES vitals(vital_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. Recommendations
CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id   INT AUTO_INCREMENT PRIMARY KEY,
    patient_id          INT NOT NULL,
    vital_id            INT NULL,
    ews_id              INT NULL,
    from_ward           ENUM('ICU', 'HDU', 'General') NOT NULL,
    to_ward             ENUM('ICU', 'HDU', 'General') NOT NULL,
    score               INT DEFAULT 0,
    confidence          FLOAT DEFAULT 0.0,
    recommendation_text TEXT NOT NULL,
    reason              TEXT NULL,
    status              ENUM('pending', 'approved', 'rejected', 'auto') DEFAULT 'pending',
    decided_by          INT NULL,
    decided_at          TIMESTAMP NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (vital_id) REFERENCES vitals(vital_id) ON DELETE SET NULL,
    FOREIGN KEY (ews_id) REFERENCES ews_scores(ews_id) ON DELETE SET NULL,
    FOREIGN KEY (decided_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. Transfers
CREATE TABLE IF NOT EXISTS transfers (
    transfer_id         INT AUTO_INCREMENT PRIMARY KEY,
    patient_id          INT NOT NULL,
    recommendation_id   INT NULL,
    from_ward           ENUM('ICU', 'HDU', 'General') NOT NULL,
    to_ward             ENUM('ICU', 'HDU', 'General') NOT NULL,
    from_bed_id         INT NULL,
    to_bed_id           INT NULL,
    from_bed_number     VARCHAR(20) NULL,
    to_bed_number       VARCHAR(20) NULL,
    transfer_reason     TEXT NULL,
    requested_by        INT NULL,
    approved_by         INT NULL,
    status              ENUM('pending', 'approved', 'completed', 'cancelled', 'rejected') NOT NULL DEFAULT 'pending',
    requested_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at        TIMESTAMP NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (recommendation_id) REFERENCES recommendations(recommendation_id) ON DELETE SET NULL,
    FOREIGN KEY (from_bed_id) REFERENCES beds(bed_id) ON DELETE SET NULL,
    FOREIGN KEY (to_bed_id) REFERENCES beds(bed_id) ON DELETE SET NULL,
    FOREIGN KEY (requested_by) REFERENCES users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (approved_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9. Notifications
CREATE TABLE IF NOT EXISTS notifications (
    notification_id     INT AUTO_INCREMENT PRIMARY KEY,
    user_id             INT NOT NULL,
    patient_id          INT NULL,
    type                ENUM('alert', 'transfer', 'system', 'ews', 'broadcast') NOT NULL DEFAULT 'system',
    title               VARCHAR(200) NOT NULL,
    message             TEXT NOT NULL,
    is_read             BOOLEAN DEFAULT FALSE,
    read_at             TIMESTAMP NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 10. Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id             INT NULL,
    action              VARCHAR(100) NOT NULL,
    entity_type         VARCHAR(50) NULL,
    entity_id           INT NULL,
    old_value           JSON NULL,
    new_value           JSON NULL,
    ip_address          VARCHAR(45) NULL,
    description         TEXT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;
