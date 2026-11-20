-- Migration 011: Add availability duty status to doctors and nurses tables
-- Keeps working availability strictly isolated from account status (users.is_active).
-- Non-destructive addition with safe default 'active'.

ALTER TABLE `doctors`
ADD COLUMN `availability` ENUM('active', 'inactive') NOT NULL DEFAULT 'active' AFTER `experience_years`;

ALTER TABLE `nurses`
ADD COLUMN `availability` ENUM('active', 'inactive') NOT NULL DEFAULT 'active' AFTER `shift`;

