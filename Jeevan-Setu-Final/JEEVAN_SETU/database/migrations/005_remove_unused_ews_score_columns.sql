-- Migration: 005_remove_unused_ews_score_columns.sql
-- Description: Drop unused spo2_score and consciousness_score columns from ews_scores table.

ALTER TABLE ews_scores DROP COLUMN spo2_score;
ALTER TABLE ews_scores DROP COLUMN consciousness_score;
