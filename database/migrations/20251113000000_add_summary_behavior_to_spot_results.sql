-- Add summary and behavior columns to spot_results table
-- Migration: 2025-11-13
-- Purpose: Add summary (TEXT) and behavior (TEXT) columns for dashboard display

ALTER TABLE spot_results
ADD COLUMN IF NOT EXISTS summary TEXT,
ADD COLUMN IF NOT EXISTS behavior TEXT;

-- Add comments
COMMENT ON COLUMN spot_results.summary IS 'Analysis summary for dashboard display (e.g., "朝食の時間。家族と一緒に食事をしている。")';
COMMENT ON COLUMN spot_results.behavior IS 'Detected behavior pattern (e.g., "食事, 家族団らん")';
