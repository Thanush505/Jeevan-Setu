-- Migration: 006_add_patient_name_to_decisions.sql
-- Description: Add patient_name column to decisions table and backfill from patients table.

ALTER TABLE decisions ADD COLUMN patient_name VARCHAR(150) NULL AFTER patient_id;

UPDATE decisions d
JOIN patients p ON d.patient_id = p.patient_id
SET d.patient_name = p.name
WHERE d.patient_name IS NULL;
