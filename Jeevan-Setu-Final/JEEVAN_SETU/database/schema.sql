-- =============================================================
-- JEEVAN SETU — Complete Authoritative Database Schema
-- Smart ICU/HDU Patient Monitoring & Clinical Decision Support
-- Auto-synchronized with live MySQL Database
-- =============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- 1. Table: roles
CREATE TABLE IF NOT EXISTS `roles` (
  `role_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `display_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`role_id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Table: users
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
) ENGINE=InnoDB AUTO_INCREMENT=123 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 3. Table: doctors
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
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Table: nurses
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
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Table: wards
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
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=115 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Table: patients
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
) ENGINE=InnoDB AUTO_INCREMENT=66 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 8. Table: attendants
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
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 9. Table: bed_management
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
) ENGINE=InnoDB AUTO_INCREMENT=58 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Table: vitals
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
) ENGINE=InnoDB AUTO_INCREMENT=118 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 11. Table: ews_scores
CREATE TABLE IF NOT EXISTS `ews_scores` (
  `ews_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `patient_name` varchar(150) DEFAULT NULL,
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
) ENGINE=InnoDB AUTO_INCREMENT=97 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 12. Table: decisions
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
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 13. Table: recommendations
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
) ENGINE=InnoDB AUTO_INCREMENT=64 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 14. Table: explanations
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
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 15. Table: transfers
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
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 16. Table: reports
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
) ENGINE=InnoDB AUTO_INCREMENT=113 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 17. Table: alerts
CREATE TABLE IF NOT EXISTS `alerts` (
  `alert_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `alert_type` enum('critical','high','medium','low','info') NOT NULL,
  `title` varchar(200) NOT NULL,
  `message` text NOT NULL,
  `parameter` varchar(50) DEFAULT NULL,
  `value` float DEFAULT NULL,
  `threshold` float DEFAULT NULL,
  `is_acknowledged` tinyint(1) DEFAULT '0',
  `acknowledged_by` int DEFAULT NULL,
  `acknowledged_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`alert_id`),
  KEY `acknowledged_by` (`acknowledged_by`),
  KEY `idx_alerts_patient` (`patient_id`),
  KEY `idx_alerts_acknowledged` (`is_acknowledged`),
  KEY `idx_alerts_type` (`alert_type`),
  CONSTRAINT `alerts_ibfk_1` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `alerts_ibfk_2` FOREIGN KEY (`acknowledged_by`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 18. Table: notifications
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
) ENGINE=InnoDB AUTO_INCREMENT=476 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 19. Table: patient_qr_tokens
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
) ENGINE=InnoDB AUTO_INCREMENT=32 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 20. Table: chatbot_conversations
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
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 21. Table: token_blacklist
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
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 22. Table: audit_logs
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
) ENGINE=InnoDB AUTO_INCREMENT=209 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 23. Table: schema_migrations
CREATE TABLE IF NOT EXISTS `schema_migrations` (
  `migration_id` int NOT NULL AUTO_INCREMENT,
  `version` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `applied_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`migration_id`),
  UNIQUE KEY `version` (`version`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- SEED DATA — Realistic Hospital Dataset for Jeevan Setu
-- 10 Admitted Patients, 3 Doctors, 3 Nurses, 1 Admin, 10 Attendants
-- 2 Wards (ICU-A, HDU-B, 20 Beds each), Live Beds & Allocations
-- =============================================================

-- 1. Roles
INSERT INTO roles (role_id, name, display_name, description) VALUES
  (1, 'admin', 'Administrator', 'Full system access'),
  (2, 'doctor', 'Doctor', 'Clinical decision-making and patient care'),
  (3, 'nurse', 'Nurse', 'Vital signs recording and patient monitoring'),
  (4, 'attendant', 'Patient Attendant', 'Read-only patient status access')
ON DUPLICATE KEY UPDATE display_name = VALUES(display_name), description = VALUES(description);

-- 2. Users (1 Admin + 3 Doctors + 3 Nurses + 10 Attendants)
INSERT INTO users (user_id, username, password_hash, full_name, email, role_id, role, department, is_active) VALUES
  (1,  'admin_js',     'Admin@123',     'System Administrator', 'admin@jeevansetu.in',         1, 'admin',     'Administration', 1),
  (2,  'dr_sharma',    'Doctor@123',    'Dr. Anil Sharma',      'anil.sharma@jeevansetu.in',   2, 'doctor',    'Cardiology',     1),
  (3,  'dr_patel',     'Doctor@123',    'Dr. Kavita Patel',     'kavita.patel@jeevansetu.in',  2, 'doctor',    'Pulmonology',    1),
  (4,  'dr_gupta',     'Doctor@123',    'Dr. Rajiv Gupta',      'rajiv.gupta@jeevansetu.in',   2, 'doctor',    'Neurology',      1),
  (5,  'nurse_priya',  'Nurse@123',     'Priya Menon',          'priya.menon@jeevansetu.in',   3, 'nurse',     'ICU',            1),
  (6,  'nurse_arun',   'Nurse@123',     'Arun Krishnan',        'arun.krishnan@jeevansetu.in', 3, 'nurse',     'HDU',            1),
  (7,  'nurse_meera',  'Nurse@123',     'Meera Jain',           'meera.jain@jeevansetu.in',    3, 'nurse',     'ICU',            1),
  (8,  'att_rajesh',   'Attendant@123', 'Suman Kumar',          'suman.kumar@email.com',       4, 'attendant', NULL,             1),
  (9,  'att_anita',    'Attendant@123', 'Ramesh Devi',          'ramesh.devi@email.com',       4, 'attendant', NULL,             1),
  (10, 'att_vikram',   'Attendant@123', 'Geeta Singh',          'geeta.singh@email.com',       4, 'attendant', NULL,             1),
  (11, 'att_sunita',   'Attendant@123', 'Prakash Rao',          'prakash.rao@email.com',       4, 'attendant', NULL,             1),
  (12, 'att_mohammed', 'Attendant@123', 'Fatima Ali',           'fatima.ali@email.com',        4, 'attendant', NULL,             1),
  (13, 'att_priya_n',  'Attendant@123', 'Suresh Nair',          'suresh.nair@email.com',       4, 'attendant', NULL,             1),
  (14, 'att_amit',     'Attendant@123', 'Kavita Verma',         'kavita.verma@email.com',      4, 'attendant', NULL,             1),
  (15, 'att_lakshmi',  'Attendant@123', 'Ganesh Iyer',          'ganesh.iyer@email.com',       4, 'attendant', NULL,             1),
  (16, 'att_deepak',   'Attendant@123', 'Rani Joshi',           'rani.joshi@email.com',        4, 'attendant', NULL,             1),
  (17, 'att_fatima',   'Attendant@123', 'Ahmed Begum',          'ahmed.begum@email.com',       4, 'attendant', NULL,             1)
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name), email = VALUES(email), role = VALUES(role);

-- 3. Doctors Profile
INSERT INTO doctors (user_id, username, password_hash, full_name, email, specialization, license_number, qualification, experience_years, is_active) VALUES
  (2, 'dr_sharma', 'Doctor@123', 'Dr. Anil Sharma', 'anil.sharma@jeevansetu.in', 'Cardiology',  'MCI-KA-2008-04521', 'MD Medicine, DM Cardiology (AIIMS Delhi)',        18, 1),
  (3, 'dr_patel',  'Doctor@123', 'Dr. Kavita Patel', 'kavita.patel@jeevansetu.in', 'Pulmonology', 'MCI-MH-2012-07834', 'MD Pulmonary Medicine (KEM Mumbai)',            14, 1),
  (4, 'dr_gupta',  'Doctor@123', 'Dr. Rajiv Gupta',  'rajiv.gupta@jeevansetu.in',  'Neurology',   'MCI-DL-2010-06219', 'MD Medicine, DM Neurology (NIMHANS Bangalore)', 16, 1)
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name), specialization = VALUES(specialization);

-- 4. Nurses Profile
INSERT INTO nurses (user_id, username, password_hash, full_name, email, specialization, license_number, qualification, ward_assignment, shift, experience_years, is_active) VALUES
  (5, 'nurse_priya', 'Nurse@123', 'Priya Menon',   'priya.menon@jeevansetu.in',   'Critical Care Nursing', 'NMC-KL-2015-11234', 'BSc Nursing, Post Basic ICU Certification', 'ICU', 'Day',       11, 1),
  (6, 'nurse_arun',  'Nurse@123', 'Arun Krishnan', 'arun.krishnan@jeevansetu.in', 'General Nursing',       'NMC-KL-2017-13567', 'BSc Nursing (CMC Vellore)',                 'HDU', 'Night',     9,  1),
  (7, 'nurse_meera', 'Nurse@123', 'Meera Jain',    'meera.jain@jeevansetu.in',    'Emergency Nursing',     'NMC-RJ-2016-12890', 'BSc Nursing, ACLS Certified',               'ICU', 'Rotating', 10, 1)
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name), ward_assignment = VALUES(ward_assignment);

-- 5. Wards (ICU-A and HDU-B, 20 Beds Capacity each)
INSERT INTO wards (ward_id, name, ward_type, floor_number, total_beds, description, is_active) VALUES
  (1, 'ICU-A', 'ICU', 2, 20, 'Intensive Care Unit - Wing A, Floor 2 (Level 3 Monitoring)', 1),
  (2, 'HDU-B', 'HDU', 3, 20, 'High Dependency Unit - Wing B, Floor 3 (Step-Down Care)', 1)
ON DUPLICATE KEY UPDATE total_beds = VALUES(total_beds), description = VALUES(description);

-- 6. Beds (ICU-A01 to ICU-A20 for ICU-A, HDU-B01 to HDU-B20 for HDU-B)
INSERT INTO beds (bed_id, ward_id, bed_number, status, is_active) VALUES
  (1,  1, 'ICU-A01', 'occupied',  1), (2,  1, 'ICU-A02', 'occupied',  1), (3,  1, 'ICU-A03', 'occupied',  1),
  (4,  1, 'ICU-A04', 'occupied',  1), (5,  1, 'ICU-A05', 'occupied',  1), (6,  1, 'ICU-A06', 'occupied',  1),
  (85, 1, 'ICU-A07', 'available', 1), (86, 1, 'ICU-A08', 'available', 1), (87, 1, 'ICU-A09', 'available', 1),
  (88, 1, 'ICU-A10', 'available', 1), (95, 1, 'ICU-A11', 'available', 1), (96, 1, 'ICU-A12', 'available', 1),
  (97, 1, 'ICU-A13', 'available', 1), (98, 1, 'ICU-A14', 'available', 1), (99, 1, 'ICU-A15', 'available', 1),
  (100, 1, 'ICU-A16', 'available', 1), (101, 1, 'ICU-A17', 'available', 1), (102, 1, 'ICU-A18', 'available', 1),
  (103, 1, 'ICU-A19', 'available', 1), (104, 1, 'ICU-A20', 'available', 1),
  (7,  2, 'HDU-B01', 'occupied',  1), (8,  2, 'HDU-B02', 'occupied',  1), (9,  2, 'HDU-B03', 'occupied',  1),
  (10, 2, 'HDU-B04', 'occupied',  1), (89, 2, 'HDU-B05', 'available', 1), (90, 2, 'HDU-B06', 'available', 1),
  (91, 2, 'HDU-B07', 'available', 1), (92, 2, 'HDU-B08', 'available', 1), (93, 2, 'HDU-B09', 'available', 1),
  (94, 2, 'HDU-B10', 'available', 1), (105, 2, 'HDU-B11', 'available', 1), (106, 2, 'HDU-B12', 'available', 1),
  (107, 2, 'HDU-B13', 'available', 1), (108, 2, 'HDU-B14', 'available', 1), (109, 2, 'HDU-B15', 'available', 1),
  (110, 2, 'HDU-B16', 'available', 1), (111, 2, 'HDU-B17', 'available', 1), (112, 2, 'HDU-B18', 'available', 1),
  (113, 2, 'HDU-B19', 'available', 1), (114, 2, 'HDU-B20', 'available', 1)
ON DUPLICATE KEY UPDATE status = VALUES(status), is_active = VALUES(is_active);

-- 7. Patients (The 10 Approved Canonical Patients)
-- Doctor 2 & Nurse 5: Patients 1-3 (3)
-- Doctor 3 & Nurse 6: Patients 4-6 (3)
-- Doctor 4 & Nurse 7: Patients 7-10 (4)
INSERT INTO patients (patient_id, patient_code, name, age, gender, blood_group, contact_number, emergency_contact, admission_date, ward_id, bed_id, ward_type, bed_number, diagnosis, status, assigned_doctor, assigned_nurse, created_by) VALUES
  (1,  'UHID-2026-00001', 'Rajesh Kumar', 58, 'Male',   'B+',  '+91 98765 43210', '+91 98765 43211', DATE_SUB(NOW(), INTERVAL 72 HOUR), 1, 1,  'ICU', 'ICU-A01', 'Acute Respiratory Distress Syndrome (ARDS) & Sepsis', 'admitted', 2, 5, 1),
  (2,  'UHID-2026-00002', 'Anita Devi',   45, 'Female', 'O+',  '+91 98765 43212', '+91 98765 43213', DATE_SUB(NOW(), INTERVAL 48 HOUR), 1, 2,  'ICU', 'ICU-A02', 'Post-Operative Coronary Artery Bypass Graft (CABG)',      'admitted', 2, 5, 1),
  (3,  'UHID-2026-00003', 'Vikram Singh', 62, 'Male',   'A+',  '+91 98765 43214', '+91 98765 43215', DATE_SUB(NOW(), INTERVAL 36 HOUR), 1, 3,  'ICU', 'ICU-A03', 'Severe Polytrauma & Traumatic Brain Injury (TBI)',         'admitted', 2, 5, 1),
  (4,  'UHID-2026-00004', 'Sunita Rao',   51, 'Female', 'AB+', '+91 98765 43216', '+91 98765 43217', DATE_SUB(NOW(), INTERVAL 60 HOUR), 1, 4,  'ICU', 'ICU-A04', 'Acute Kidney Injury (AKI) & Metabolic Acidosis',          'admitted', 3, 6, 1),
  (5,  'UHID-2026-00005', 'Mohammed Ali', 40, 'Male',   'O-',  '+91 98765 43218', '+91 98765 43219', DATE_SUB(NOW(), INTERVAL 24 HOUR), 1, 5,  'ICU', 'ICU-A05', 'Severe Acute Pancreatitis',                              'admitted', 3, 6, 1),
  (6,  'UHID-2026-00006', 'Priya Nair',   33, 'Female', 'B-',  '+91 98765 43220', '+91 98765 43221', DATE_SUB(NOW(), INTERVAL 18 HOUR), 1, 6,  'ICU', 'ICU-A06', 'Post-Partum Hemorrhage (PPH) & Hypovolemic Shock',         'admitted', 3, 6, 1),
  (7,  'UHID-2026-00007', 'Amit Verma',   55, 'Male',   'A-',  '+91 98765 43222', '+91 98765 43223', DATE_SUB(NOW(), INTERVAL 96 HOUR), 2, 7,  'HDU', 'HDU-B01', 'Decompensated Heart Failure (NYHA Class IV)',            'admitted', 4, 7, 1),
  (8,  'UHID-2026-00008', 'Lakshmi Iyer', 29, 'Female', 'AB-', '+91 98765 43224', '+91 98765 43225', DATE_SUB(NOW(), INTERVAL 42 HOUR), 2, 8,  'HDU', 'HDU-B02', 'Diabetic Ketoacidosis (DKA) - Resolving Phase',           'admitted', 4, 7, 1),
  (9,  'UHID-2026-00009', 'Deepak Joshi', 47, 'Male',   'B+',  '+91 98765 43226', '+91 98765 43227', DATE_SUB(NOW(), INTERVAL 30 HOUR), 2, 9,  'HDU', 'HDU-B03', 'Community Acquired Pneumonia (CAP) & COPD Exacerbation',  'admitted', 4, 7, 1),
  (10, 'UHID-2026-00010', 'Fatima Begum', 65, 'Female', 'O+',  '+91 98765 43228', '+91 98765 43229', DATE_SUB(NOW(), INTERVAL 12 HOUR), 2, 10, 'HDU', 'HDU-B04', 'Acute Ischemic Stroke (Subacute Recovery Phase)',          'admitted', 4, 7, 1)
ON DUPLICATE KEY UPDATE name = VALUES(name), diagnosis = VALUES(diagnosis), status = VALUES(status);

-- 8. Attendants Mapping (User IDs 8-17 to Patients 1-10)
INSERT INTO attendants (patient_id, user_id, relationship, access_code) VALUES
  (1,  8,  'Spouse',   'JSACC10001'),
  (2,  9,  'Son',      'JSACC10002'),
  (3,  10, 'Daughter', 'JSACC10003'),
  (4,  11, 'Spouse',   'JSACC10004'),
  (5,  12, 'Wife',     'JSACC10005'),
  (6,  13, 'Brother',  'JSACC10006'),
  (7,  14, 'Wife',     'JSACC10007'),
  (8,  15, 'Father',   'JSACC10008'),
  (9,  16, 'Wife',     'JSACC10009'),
  (10, 17, 'Son',      'JSACC10010')
ON DUPLICATE KEY UPDATE relationship = VALUES(relationship), access_code = VALUES(access_code);

-- 9. Bed Management (Active Allocations for Patients 1-10)
INSERT INTO bed_management (patient_id, bed_id, ward_id, allocated_at, status, allocated_by, notes) VALUES
  (1,  1,  1, DATE_SUB(NOW(), INTERVAL 72 HOUR), 'occupied', 1, 'Admission allocation'),
  (2,  2,  1, DATE_SUB(NOW(), INTERVAL 48 HOUR), 'occupied', 1, 'Admission allocation'),
  (3,  3,  1, DATE_SUB(NOW(), INTERVAL 36 HOUR), 'occupied', 1, 'Admission allocation'),
  (4,  4,  1, DATE_SUB(NOW(), INTERVAL 60 HOUR), 'occupied', 1, 'Admission allocation'),
  (5,  5,  1, DATE_SUB(NOW(), INTERVAL 24 HOUR), 'occupied', 1, 'Admission allocation'),
  (6,  6,  1, DATE_SUB(NOW(), INTERVAL 18 HOUR), 'occupied', 1, 'Admission allocation'),
  (7,  7,  2, DATE_SUB(NOW(), INTERVAL 96 HOUR), 'occupied', 1, 'Admission allocation'),
  (8,  8,  2, DATE_SUB(NOW(), INTERVAL 42 HOUR), 'occupied', 1, 'Admission allocation'),
  (9,  9,  2, DATE_SUB(NOW(), INTERVAL 30 HOUR), 'occupied', 1, 'Admission allocation'),
  (10, 10, 2, DATE_SUB(NOW(), INTERVAL 12 HOUR), 'occupied', 1, 'Admission allocation')
ON DUPLICATE KEY UPDATE status = VALUES(status);

-- 10. Schema Migrations History
INSERT INTO schema_migrations (version, description) VALUES
  ('001_core_schema', 'Initial database schema creation for Jeevan Setu'),
  ('002_rbac_system', 'Role-based access control setup'),
  ('003_seed_data', 'Realistic clinical dataset with 10 patients and 20-bed wards'),
  ('seed_v1_2026', 'Authoritative verified seed data snapshot')
ON DUPLICATE KEY UPDATE description = VALUES(description);

SET FOREIGN_KEY_CHECKS = 1;
