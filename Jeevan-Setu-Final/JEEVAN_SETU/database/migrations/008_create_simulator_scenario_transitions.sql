-- Migration 008: Create Simulator Patient States & Scenario Transitions Tracking
-- Non-destructive: Supports persistent telemetry scenario states and test auditing

CREATE TABLE IF NOT EXISTS simulator_patient_states (
    patient_id INT PRIMARY KEY,
    current_scenario VARCHAR(50) NOT NULL DEFAULT 'STABLE',
    previous_scenario VARCHAR(50) DEFAULT NULL,
    transition_status VARCHAR(50) DEFAULT 'ACTIVE',
    last_transition_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by INT DEFAULT NULL,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS simulator_scenario_transitions (
    transition_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    source_scenario VARCHAR(50) NOT NULL,
    target_scenario VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'SUCCESS',
    error_message TEXT DEFAULT NULL,
    transition_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    initiated_by VARCHAR(100) DEFAULT 'DEVELOPER_TESTER',
    user_id INT DEFAULT NULL,
    metadata JSON DEFAULT NULL,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
    INDEX idx_patient_time (patient_id, transition_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Initialize baseline simulator states for admitted patients (default to STABLE)
INSERT IGNORE INTO simulator_patient_states (patient_id, current_scenario, previous_scenario, transition_status)
SELECT patient_id, 'STABLE', NULL, 'ACTIVE' FROM patients WHERE status = 'admitted';
