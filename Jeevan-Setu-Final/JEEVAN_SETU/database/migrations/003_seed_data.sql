-- Migration: 003_seed_data.sql
-- Description: Seed initial default roles, wards, and beds

SET FOREIGN_KEY_CHECKS = 0;

-- 1. Insert Core Roles
INSERT IGNORE INTO roles (name, display_name, description) VALUES
('admin', 'System Administrator', 'Full administrative access and user management'),
('doctor', 'Attending Doctor / Physician', 'Clinical decision approvals, patient management, vitals diagnosis'),
('nurse', 'Staff Nurse', 'Vitals logging, patient intake, bed monitoring'),
('attendant', 'Patient Attendant', 'Restricted patient view access via QR / security code');

-- 2. Insert Default Wards
INSERT IGNORE INTO wards (name, ward_type, floor_number, total_beds, description) VALUES
('Intensive Care Unit (ICU-1)', 'ICU', 2, 10, 'Primary Critical Care Unit with Level 3 Monitoring'),
('High Dependency Unit (HDU-1)', 'HDU', 2, 10, 'Step-down High Dependency Unit for stabilizing patients'),
('General Ward North', 'General', 3, 20, 'Post-recovery and General Observation Ward');

-- 3. Insert Initial Beds for Wards
-- ICU-1 Beds (Ward 1)
INSERT IGNORE INTO beds (ward_id, bed_number, status) VALUES
(1, 'ICU-101', 'available'),
(1, 'ICU-102', 'available'),
(1, 'ICU-103', 'available'),
(1, 'ICU-104', 'available'),
(1, 'ICU-105', 'available'),
(1, 'ICU-106', 'available'),
(1, 'ICU-107', 'available'),
(1, 'ICU-108', 'available'),
(1, 'ICU-109', 'available'),
(1, 'ICU-110', 'available');

-- HDU-1 Beds (Ward 2)
INSERT IGNORE INTO beds (ward_id, bed_number, status) VALUES
(2, 'HDU-201', 'available'),
(2, 'HDU-202', 'available'),
(2, 'HDU-203', 'available'),
(2, 'HDU-204', 'available'),
(2, 'HDU-205', 'available'),
(2, 'HDU-206', 'available'),
(2, 'HDU-207', 'available'),
(2, 'HDU-208', 'available'),
(2, 'HDU-209', 'available'),
(2, 'HDU-210', 'available');

-- General Ward Beds (Ward 3)
INSERT IGNORE INTO beds (ward_id, bed_number, status) VALUES
(3, 'GEN-301', 'available'),
(3, 'GEN-302', 'available'),
(3, 'GEN-303', 'available'),
(3, 'GEN-304', 'available'),
(3, 'GEN-305', 'available');

SET FOREIGN_KEY_CHECKS = 1;
