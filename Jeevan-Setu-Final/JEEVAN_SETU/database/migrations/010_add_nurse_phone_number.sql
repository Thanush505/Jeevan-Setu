-- Migration 010: Add contact/phone number to nurses and users
-- Non-destructive, nullable addition preserving all existing records.

ALTER TABLE `nurses` 
ADD COLUMN `phone_number` VARCHAR(20) NULL DEFAULT NULL AFTER `email`;

ALTER TABLE `users` 
ADD COLUMN `contact_number` VARCHAR(20) NULL DEFAULT NULL AFTER `email`;
