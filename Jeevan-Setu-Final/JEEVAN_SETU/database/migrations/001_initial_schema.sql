-- Migration: 001_initial_schema.sql
-- Description: Core tables for users, patients, vitals, alerts, attendants, decisions, explanations, chatbot, reports, audit_log

CREATE TABLE IF NOT EXISTS users (
    user_id         INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(100) UNIQUE NOT NULL,
    role            ENUM('admin', 'doctor', 'nurse', 'attendant') NOT NULL DEFAULT 'nurse',
    department      VARCHAR(50),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS patients (
    patient_id      INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    age             INT NOT NULL,
    gender          ENUM('Male', 'Female', 'Other') NOT NULL,
    blood_group     VARCHAR(5),
    contact_number  VARCHAR(15),
    admission_date  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    discharge_date  DATETIME NULL,
    ward_type       ENUM('ICU', 'HDU', 'General') NOT NULL DEFAULT 'ICU',
    bed_number      VARCHAR(10),
    diagnosis       TEXT,
    status          ENUM('admitted', 'discharged', 'transferred', 'deceased') DEFAULT 'admitted',
    assigned_doctor INT,
    created_by      INT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_doctor) REFERENCES users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS vitals (
    vital_id        INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    heart_rate      FLOAT,
    blood_pressure_sys FLOAT,
    blood_pressure_dia FLOAT,
    respiratory_rate FLOAT,
    temperature     FLOAT,
    spo2            FLOAT,
    consciousness   ENUM('Alert', 'Voice', 'Pain', 'Unresponsive') DEFAULT 'Alert',
    urine_output    FLOAT,
    blood_sugar     FLOAT,
    ews_score       INT DEFAULT 0,
    recorded_by     INT,
    recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    alert_type      ENUM('critical', 'high', 'medium', 'low', 'info') NOT NULL,
    title           VARCHAR(200) NOT NULL,
    message         TEXT NOT NULL,
    parameter       VARCHAR(50),
    value           FLOAT,
    threshold       FLOAT,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by INT NULL,
    acknowledged_at TIMESTAMP NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (acknowledged_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS attendants (
    attendant_id    INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    user_id         INT NOT NULL,
    relationship    VARCHAR(50),
    access_code     VARCHAR(50) UNIQUE NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS decisions (
    decision_id     INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT NOT NULL,
    patient_name    VARCHAR(150) NULL,
    vital_id        INT,
    from_ward       ENUM('ICU', 'HDU', 'General') NOT NULL,
    to_ward         ENUM('ICU', 'HDU', 'General') NOT NULL,
    ews_score       INT,
    confidence      FLOAT,
    recommendation  TEXT NOT NULL,
    status          ENUM('pending', 'approved', 'rejected', 'auto') DEFAULT 'pending',
    decided_by      INT NULL,
    decided_at      TIMESTAMP NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    FOREIGN KEY (vital_id) REFERENCES vitals(vital_id) ON DELETE SET NULL,
    FOREIGN KEY (decided_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS explanations (
    explanation_id  INT AUTO_INCREMENT PRIMARY KEY,
    decision_id     INT NOT NULL,
    patient_id      INT NOT NULL,
    feature_name    VARCHAR(50) NOT NULL,
    feature_value   FLOAT,
    contribution    FLOAT,
    importance_rank INT,
    explanation_text TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (decision_id) REFERENCES decisions(decision_id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS chatbot_conversations (
    conversation_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    patient_id      INT NULL,
    user_message    TEXT NOT NULL,
    bot_response    TEXT NOT NULL,
    intent          VARCHAR(100),
    confidence      FLOAT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reports (
    report_id       INT AUTO_INCREMENT PRIMARY KEY,
    patient_id      INT,
    report_type     ENUM('daily', 'weekly', 'discharge', 'transfer', 'custom', 'ews', 'utilization') NOT NULL,
    title           VARCHAR(200) NOT NULL,
    content         LONGTEXT,
    file_path       VARCHAR(500),
    generated_by    INT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE SET NULL,
    FOREIGN KEY (generated_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS audit_log (
    log_id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT,
    action          VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(50),
    entity_id       INT,
    old_value       JSON,
    new_value       JSON,
    ip_address      VARCHAR(45),
    description     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
