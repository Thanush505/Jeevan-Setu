-- =============================================================
-- JEEVAN SETU — Complete Live Database Schema (schema.sql)
-- Smart ICU/HDU Patient Monitoring & Clinical Decision Support
-- Scanned and synchronized on 2026-10-11 14:14:13
-- =============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- 1. Table: alerts
CREATE TABLE IF NOT EXISTS `alerts` (
  `alert_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `alert_type` enum('critical','high','medium','low','info') NOT NULL,
  `status` varchar(20) DEFAULT 'ACTIVE',
  `title` varchar(200) NOT NULL,
  `message` text NOT NULL,
  `parameter` varchar(50) DEFAULT NULL,
  `value` float DEFAULT NULL,
  `threshold` float DEFAULT NULL,
  `is_acknowledged` tinyint(1) DEFAULT '0',
  `is_dismissed` tinyint(1) DEFAULT '0',
  `acknowledged_by` int DEFAULT NULL,
  `dismissed_by` int DEFAULT NULL,
  `acknowledged_at` timestamp NULL DEFAULT NULL,
  `dismissed_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`alert_id`),
  KEY `acknowledged_by` (`acknowledged_by`),
  KEY `idx_alerts_patient` (`patient_id`),
  KEY `idx_alerts_acknowledged` (`is_acknowledged`),
  KEY `idx_alerts_type` (`alert_type`),
  CONSTRAINT `alerts_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `alerts_ibfk_2` FOREIGN KEY (`acknowledged_by`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=448 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 2. Table: attendants
CREATE TABLE IF NOT EXISTS `attendants` (
  `attendant_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `user_id` int NOT NULL,
  `relationship` varchar(50) DEFAULT NULL,
  `access_code` varchar(20) NOT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`attendant_id`),
  UNIQUE KEY `access_code` (`access_code`),
  KEY `patient_id` (`patient_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `attendants_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `attendants_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=27 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 3. Table: audit_log
CREATE TABLE IF NOT EXISTS `audit_log` (
  `log_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `action` varchar(100) NOT NULL,
  `entity_type` varchar(50) DEFAULT NULL,
  `entity_id` int DEFAULT NULL,
  `old_value` json DEFAULT NULL,
  `new_value` json DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `description` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`log_id`),
  KEY `idx_audit_user` (`user_id`),
  KEY `idx_audit_entity` (`entity_type`,`entity_id`),
  CONSTRAINT `audit_log_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 4. Table: audit_logs
CREATE TABLE IF NOT EXISTS `audit_logs` (
  `log_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `action` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `entity_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `entity_id` int DEFAULT NULL,
  `old_value` json DEFAULT NULL,
  `new_value` json DEFAULT NULL,
  `ip_address` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`log_id`),
  KEY `idx_audit_logs_user` (`user_id`),
  KEY `idx_audit_logs_entity` (`entity_type`,`entity_id`),
  CONSTRAINT `audit_logs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=5186 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Table: bed_management
CREATE TABLE IF NOT EXISTS `bed_management` (
  `allocation_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `bed_id` int NOT NULL,
  `ward_id` int NOT NULL,
  `allocated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `released_at` datetime DEFAULT NULL,
  `status` enum('allocated','occupied','released','transferred') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'allocated',
  `allocated_by` int DEFAULT NULL,
  `notes` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`allocation_id`),
  KEY `ward_id` (`ward_id`),
  KEY `allocated_by` (`allocated_by`),
  KEY `idx_bed_mgmt_patient` (`patient_id`),
  KEY `idx_bed_mgmt_bed` (`bed_id`),
  KEY `idx_bed_mgmt_status` (`status`),
  CONSTRAINT `bed_management_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `bed_management_ibfk_2` FOREIGN KEY (`bed_id`) REFERENCES `beds` (`bed_id`) ON DELETE RESTRICT,
  CONSTRAINT `bed_management_ibfk_3` FOREIGN KEY (`ward_id`) REFERENCES `wards` (`ward_id`) ON DELETE RESTRICT,
  CONSTRAINT `bed_management_ibfk_4` FOREIGN KEY (`allocated_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=305 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Table: beds
CREATE TABLE IF NOT EXISTS `beds` (
  `bed_id` int NOT NULL AUTO_INCREMENT,
  `ward_id` int NOT NULL,
  `bed_number` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('available','occupied','maintenance','reserved') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'available',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`bed_id`),
  UNIQUE KEY `uk_ward_bed` (`ward_id`,`bed_number`),
  KEY `idx_beds_ward` (`ward_id`),
  KEY `idx_beds_status` (`status`),
  CONSTRAINT `beds_ibfk_1` FOREIGN KEY (`ward_id`) REFERENCES `wards` (`ward_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=428 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Table: chatbot_conversations
CREATE TABLE IF NOT EXISTS `chatbot_conversations` (
  `conversation_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `patient_id` int DEFAULT NULL,
  `user_message` text NOT NULL,
  `bot_response` text NOT NULL,
  `intent` varchar(100) DEFAULT NULL,
  `confidence` float DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`conversation_id`),
  KEY `user_id` (`user_id`),
  KEY `patient_id` (`patient_id`),
  CONSTRAINT `chatbot_conversations_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`),
  CONSTRAINT `chatbot_conversations_ibfk_2` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=665 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 8. Table: clinical_notes
CREATE TABLE IF NOT EXISTS `clinical_notes` (
  `note_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `doctor_id` int DEFAULT NULL,
  `note_text` text,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`note_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 9. Table: decisions
CREATE TABLE IF NOT EXISTS `decisions` (
  `decision_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `patient_name` varchar(150) DEFAULT NULL,
  `vital_id` int DEFAULT NULL,
  `from_ward` enum('ICU','HDU','General') NOT NULL,
  `to_ward` enum('ICU','HDU','General') NOT NULL,
  `ews_score` int DEFAULT NULL,
  `confidence` float DEFAULT NULL,
  `recommendation` text NOT NULL,
  `status` enum('pending','approved','rejected','auto') DEFAULT 'pending',
  `decided_by` int DEFAULT NULL,
  `decided_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`decision_id`),
  KEY `vital_id` (`vital_id`),
  KEY `decided_by` (`decided_by`),
  KEY `idx_decisions_patient` (`patient_id`),
  CONSTRAINT `decisions_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `decisions_ibfk_2` FOREIGN KEY (`vital_id`) REFERENCES `vitals` (`vital_id`),
  CONSTRAINT `decisions_ibfk_3` FOREIGN KEY (`decided_by`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=106 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 10. Table: doctors
CREATE TABLE IF NOT EXISTS `doctors` (
  `doctor_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `full_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `specialization` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `license_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `qualification` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `experience_years` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`doctor_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `license_number` (`license_number`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `doctors_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=459 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 11. Table: ews_scores
CREATE TABLE IF NOT EXISTS `ews_scores` (
  `ews_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `patient_name` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `vital_id` int NOT NULL,
  `total_score` int NOT NULL DEFAULT '0',
  `risk_level` enum('LOW','MEDIUM','HIGH','CRITICAL') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'LOW',
  `hr_score` int DEFAULT '0',
  `bp_score` int DEFAULT '0',
  `rr_score` int DEFAULT '0',
  `temp_score` int DEFAULT '0',
  `calculated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ews_id`),
  KEY `vital_id` (`vital_id`),
  KEY `idx_ews_patient` (`patient_id`),
  KEY `idx_ews_risk_level` (`risk_level`),
  CONSTRAINT `ews_scores_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `ews_scores_ibfk_2` FOREIGN KEY (`vital_id`) REFERENCES `vitals` (`vital_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2969 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. Table: explanations
CREATE TABLE IF NOT EXISTS `explanations` (
  `explanation_id` int NOT NULL AUTO_INCREMENT,
  `decision_id` int NOT NULL,
  `patient_id` int NOT NULL,
  `feature_name` varchar(50) NOT NULL,
  `feature_value` float DEFAULT NULL,
  `contribution` float DEFAULT NULL,
  `importance_rank` int DEFAULT NULL,
  `explanation_text` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`explanation_id`),
  KEY `decision_id` (`decision_id`),
  KEY `patient_id` (`patient_id`),
  CONSTRAINT `explanations_ibfk_1` FOREIGN KEY (`decision_id`) REFERENCES `decisions` (`decision_id`) ON DELETE CASCADE,
  CONSTRAINT `explanations_ibfk_2` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=294 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 13. Table: notifications
CREATE TABLE IF NOT EXISTS `notifications` (
  `notification_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `patient_id` int DEFAULT NULL,
  `type` enum('alert','transfer','system','ews','broadcast') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'system',
  `title` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `message` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_read` tinyint(1) DEFAULT '0',
  `read_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`notification_id`),
  KEY `patient_id` (`patient_id`),
  KEY `idx_notif_user` (`user_id`),
  KEY `idx_notif_read` (`is_read`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `notifications_ibfk_2` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=64748 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 14. Table: nurses
CREATE TABLE IF NOT EXISTS `nurses` (
  `nurse_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `full_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `specialization` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `license_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `qualification` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ward_assignment` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `shift` enum('Day','Night','Rotating') COLLATE utf8mb4_unicode_ci DEFAULT 'Rotating',
  `experience_years` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`nurse_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `license_number` (`license_number`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `nurses_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=334 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 15. Table: password_reset_tokens
CREATE TABLE IF NOT EXISTS `password_reset_tokens` (
  `reset_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `token_hash` varchar(255) NOT NULL,
  `expires_at` datetime NOT NULL,
  `is_used` tinyint(1) DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`reset_id`),
  UNIQUE KEY `token_hash` (`token_hash`),
  KEY `idx_reset_token` (`token_hash`),
  KEY `idx_reset_user` (`user_id`),
  CONSTRAINT `password_reset_tokens_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=34 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 16. Table: patient_qr_tokens
CREATE TABLE IF NOT EXISTS `patient_qr_tokens` (
  `token_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `token_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `access_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `qr_code_data` text COLLATE utf8mb4_unicode_ci,
  `valid_from` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expires_at` datetime NOT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_by` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`token_id`),
  UNIQUE KEY `token_hash` (`token_hash`),
  KEY `created_by` (`created_by`),
  KEY `idx_qr_patient` (`patient_id`),
  KEY `idx_qr_token` (`token_hash`),
  KEY `idx_qr_active` (`is_active`),
  CONSTRAINT `patient_qr_tokens_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `patient_qr_tokens_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=636 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 17. Table: patients
CREATE TABLE IF NOT EXISTS `patients` (
  `patient_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `age` int NOT NULL,
  `gender` enum('Male','Female','Other') NOT NULL,
  `blood_group` varchar(5) DEFAULT NULL,
  `contact_number` varchar(15) DEFAULT NULL,
  `admission_date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `discharge_date` datetime DEFAULT NULL,
  `ward_type` enum('ICU','HDU','General') NOT NULL DEFAULT 'ICU',
  `bed_number` varchar(10) DEFAULT NULL,
  `diagnosis` text,
  `status` enum('admitted','discharged','transferred','deceased') DEFAULT 'admitted',
  `assigned_doctor` int DEFAULT NULL,
  `created_by` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `patient_code` varchar(50) DEFAULT NULL,
  `emergency_contact` varchar(15) DEFAULT NULL,
  `ward_id` int DEFAULT NULL,
  `bed_id` int DEFAULT NULL,
  `assigned_nurse` int DEFAULT NULL,
  PRIMARY KEY (`patient_id`),
  UNIQUE KEY `patient_code` (`patient_code`),
  KEY `created_by` (`created_by`),
  KEY `idx_patients_status` (`status`),
  KEY `idx_patients_ward` (`ward_type`),
  KEY `idx_patients_doctor` (`assigned_doctor`),
  KEY `fk_patient_ward` (`ward_id`),
  KEY `fk_patient_bed` (`bed_id`),
  KEY `idx_patients_code` (`patient_code`),
  KEY `fk_patients_nurse` (`assigned_nurse`),
  CONSTRAINT `fk_patient_bed` FOREIGN KEY (`bed_id`) REFERENCES `beds` (`bed_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_patient_ward` FOREIGN KEY (`ward_id`) REFERENCES `wards` (`ward_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_patients_nurse` FOREIGN KEY (`assigned_nurse`) REFERENCES `users` (`user_id`) ON DELETE SET NULL,
  CONSTRAINT `patients_ibfk_1` FOREIGN KEY (`assigned_doctor`) REFERENCES `users` (`user_id`),
  CONSTRAINT `patients_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 18. Table: recommendations
CREATE TABLE IF NOT EXISTS `recommendations` (
  `recommendation_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `vital_id` int DEFAULT NULL,
  `ews_id` int DEFAULT NULL,
  `from_ward` enum('ICU','HDU','General') COLLATE utf8mb4_unicode_ci NOT NULL,
  `to_ward` enum('ICU','HDU','General') COLLATE utf8mb4_unicode_ci NOT NULL,
  `score` int DEFAULT '0',
  `confidence` float DEFAULT '0',
  `recommendation_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `reason` text COLLATE utf8mb4_unicode_ci,
  `status` enum('pending','approved','rejected','auto') COLLATE utf8mb4_unicode_ci DEFAULT 'pending',
  `decided_by` int DEFAULT NULL,
  `decided_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`recommendation_id`),
  KEY `vital_id` (`vital_id`),
  KEY `ews_id` (`ews_id`),
  KEY `decided_by` (`decided_by`),
  KEY `idx_recom_patient` (`patient_id`),
  KEY `idx_recom_status` (`status`),
  CONSTRAINT `recommendations_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `recommendations_ibfk_2` FOREIGN KEY (`vital_id`) REFERENCES `vitals` (`vital_id`) ON DELETE SET NULL,
  CONSTRAINT `recommendations_ibfk_3` FOREIGN KEY (`ews_id`) REFERENCES `ews_scores` (`ews_id`) ON DELETE SET NULL,
  CONSTRAINT `recommendations_ibfk_4` FOREIGN KEY (`decided_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=3015 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 19. Table: reports
CREATE TABLE IF NOT EXISTS `reports` (
  `report_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int DEFAULT NULL,
  `report_type` enum('daily','weekly','discharge','transfer','custom') NOT NULL,
  `title` varchar(200) NOT NULL,
  `content` longtext,
  `file_path` varchar(500) DEFAULT NULL,
  `generated_by` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`report_id`),
  KEY `generated_by` (`generated_by`),
  KEY `idx_reports_patient` (`patient_id`),
  KEY `idx_reports_type` (`report_type`),
  CONSTRAINT `reports_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE SET NULL,
  CONSTRAINT `reports_ibfk_2` FOREIGN KEY (`generated_by`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=528 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 20. Table: roles
CREATE TABLE IF NOT EXISTS `roles` (
  `role_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `display_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`role_id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 21. Table: schema_migrations
CREATE TABLE IF NOT EXISTS `schema_migrations` (
  `migration_id` int NOT NULL AUTO_INCREMENT,
  `version` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `applied_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`migration_id`),
  UNIQUE KEY `version` (`version`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 22. Table: token_blacklist
CREATE TABLE IF NOT EXISTS `token_blacklist` (
  `blacklist_id` int NOT NULL AUTO_INCREMENT,
  `token_jti` varchar(255) NOT NULL,
  `token_type` varchar(50) DEFAULT 'access',
  `user_id` int DEFAULT NULL,
  `expires_at` datetime NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`blacklist_id`),
  UNIQUE KEY `token_jti` (`token_jti`),
  KEY `user_id` (`user_id`),
  KEY `idx_blacklist_jti` (`token_jti`),
  CONSTRAINT `token_blacklist_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=63 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 23. Table: transfers
CREATE TABLE IF NOT EXISTS `transfers` (
  `transfer_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `recommendation_id` int DEFAULT NULL,
  `from_ward` enum('ICU','HDU','General') COLLATE utf8mb4_unicode_ci NOT NULL,
  `to_ward` enum('ICU','HDU','General') COLLATE utf8mb4_unicode_ci NOT NULL,
  `from_bed_id` int DEFAULT NULL,
  `to_bed_id` int DEFAULT NULL,
  `from_bed_number` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `to_bed_number` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `transfer_reason` text COLLATE utf8mb4_unicode_ci,
  `requested_by` int DEFAULT NULL,
  `approved_by` int DEFAULT NULL,
  `status` enum('pending','approved','completed','cancelled','rejected') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `requested_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `completed_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`transfer_id`),
  KEY `recommendation_id` (`recommendation_id`),
  KEY `from_bed_id` (`from_bed_id`),
  KEY `to_bed_id` (`to_bed_id`),
  KEY `requested_by` (`requested_by`),
  KEY `approved_by` (`approved_by`),
  KEY `idx_transfers_patient` (`patient_id`),
  KEY `idx_transfers_status` (`status`),
  CONSTRAINT `transfers_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `transfers_ibfk_2` FOREIGN KEY (`recommendation_id`) REFERENCES `recommendations` (`recommendation_id`) ON DELETE SET NULL,
  CONSTRAINT `transfers_ibfk_3` FOREIGN KEY (`from_bed_id`) REFERENCES `beds` (`bed_id`) ON DELETE SET NULL,
  CONSTRAINT `transfers_ibfk_4` FOREIGN KEY (`to_bed_id`) REFERENCES `beds` (`bed_id`) ON DELETE SET NULL,
  CONSTRAINT `transfers_ibfk_5` FOREIGN KEY (`requested_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL,
  CONSTRAINT `transfers_ibfk_6` FOREIGN KEY (`approved_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=207 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 24. Table: user_preferences
CREATE TABLE IF NOT EXISTS `user_preferences` (
  `user_id` int NOT NULL,
  `in_app_notifications` tinyint(1) DEFAULT '1',
  `critical_patient_alerts` tinyint(1) DEFAULT '1',
  `ews_alerts` tinyint(1) DEFAULT '1',
  `task_notifications` tinyint(1) DEFAULT '1',
  `sound_alerts` tinyint(1) DEFAULT '1',
  `theme` varchar(20) DEFAULT 'light',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  CONSTRAINT `user_preferences_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 25. Table: users
CREATE TABLE IF NOT EXISTS `users` (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `full_name` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `role` enum('admin','doctor','nurse','attendant') NOT NULL DEFAULT 'nurse',
  `department` varchar(50) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `role_id` int DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  KEY `idx_users_role` (`role`),
  KEY `idx_users_email` (`email`),
  KEY `fk_user_role` (`role_id`),
  CONSTRAINT `fk_user_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`role_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=1226 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 26. Table: vitals
CREATE TABLE IF NOT EXISTS `vitals` (
  `vital_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `heart_rate` float DEFAULT NULL,
  `blood_pressure_sys` float DEFAULT NULL,
  `blood_pressure_dia` float DEFAULT NULL,
  `respiratory_rate` float DEFAULT NULL,
  `temperature` float DEFAULT NULL,
  `spo2` float DEFAULT NULL,
  `consciousness` enum('Alert','Voice','Pain','Unresponsive') DEFAULT 'Alert',
  `urine_output` float DEFAULT NULL,
  `blood_sugar` float DEFAULT NULL,
  `ews_score` int DEFAULT '0',
  `recorded_by` int DEFAULT NULL,
  `recorded_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`vital_id`),
  KEY `recorded_by` (`recorded_by`),
  KEY `idx_vitals_patient` (`patient_id`),
  KEY `idx_vitals_recorded_at` (`recorded_at`),
  CONSTRAINT `vitals_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `vitals_ibfk_2` FOREIGN KEY (`recorded_by`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3283 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 27. Table: wards
CREATE TABLE IF NOT EXISTS `wards` (
  `ward_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ward_type` enum('ICU','HDU','General') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ICU',
  `floor_number` int DEFAULT '1',
  `total_beds` int NOT NULL DEFAULT '10',
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ward_id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_wards_type` (`ward_type`)
) ENGINE=InnoDB AUTO_INCREMENT=179 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
