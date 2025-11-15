-- Migration: Recreate daily_results table with correct schema
-- Date: 2025-11-15
-- Purpose: Fix daily_results schema to match CSV structure and Profiler API requirements
--
-- Changes:
-- 1. DROP existing daily_results table (no data loss as table is empty)
-- 2. CREATE new daily_results table with correct columns
--
-- Correct Schema (based on dashboard_summary_rows.csv and Profiler API):
--   device_id, local_date, vibe_score, summary, behavior, profile_result,
--   vibe_scores, burst_events, processed_count, last_time_block,
--   llm_model, created_at, updated_at

-- ============================================================================
-- Step 1: Drop existing daily_results table
-- ============================================================================

DROP TABLE IF EXISTS daily_results CASCADE;

-- ============================================================================
-- Step 2: Create new daily_results table with correct schema
-- ============================================================================

CREATE TABLE daily_results (
  -- Primary Key
  device_id TEXT NOT NULL,
  local_date DATE NOT NULL,

  -- Analysis Results (from Profiler API)
  vibe_score REAL,                    -- Average vibe score for the day (CSV: average_vibe)
  summary TEXT,                       -- Daily insights summary in Japanese (CSV: insights)
  behavior TEXT,                      -- Detected behaviors, comma-separated (from Profiler API)
  profile_result JSONB,               -- Full LLM analysis result (CSV: analysis_result)

  -- Aggregated Data (from Aggregator API)
  vibe_scores JSONB,                  -- Array of 48 vibe scores (30-min blocks)
  burst_events JSONB,                 -- Array of significant mood change events
  processed_count INTEGER DEFAULT 0,  -- Number of spot recordings processed
  last_time_block VARCHAR(5),         -- Last time block processed (e.g., "11-00")

  -- Metadata
  llm_model TEXT,                     -- LLM model used for analysis (from Profiler API)
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  PRIMARY KEY (device_id, local_date)
);

-- ============================================================================
-- Step 3: Disable RLS (internal API use only)
-- ============================================================================

ALTER TABLE daily_results DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- Step 4: Create indexes for performance
-- ============================================================================

-- Index for device_id queries
CREATE INDEX IF NOT EXISTS idx_daily_results_device_id
  ON daily_results USING btree (device_id);

-- Index for vibe_score queries (dashboard charts)
CREATE INDEX IF NOT EXISTS idx_daily_results_vibe_score
  ON daily_results USING btree (vibe_score)
  WHERE vibe_score IS NOT NULL;

-- Index for local_date range queries
CREATE INDEX IF NOT EXISTS idx_daily_results_local_date
  ON daily_results USING btree (local_date);

-- ============================================================================
-- Step 5: Create trigger for auto-updating updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_daily_results_updated_at ON daily_results;

CREATE TRIGGER update_daily_results_updated_at
  BEFORE UPDATE ON daily_results
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Step 6: Add table and column comments
-- ============================================================================

COMMENT ON TABLE daily_results IS 'Daily cumulative analysis results (1 day = 1 record)';
COMMENT ON COLUMN daily_results.device_id IS 'Device identifier';
COMMENT ON COLUMN daily_results.local_date IS 'Local date based on device timezone';
COMMENT ON COLUMN daily_results.vibe_score IS 'Average vibe score for the day (-100 to +100)';
COMMENT ON COLUMN daily_results.summary IS 'Daily insights summary in Japanese';
COMMENT ON COLUMN daily_results.behavior IS 'Detected behaviors, comma-separated (e.g., "会話, 食事, 遊び")';
COMMENT ON COLUMN daily_results.profile_result IS 'Full LLM analysis result (JSONB)';
COMMENT ON COLUMN daily_results.vibe_scores IS 'Array of 48 vibe scores (30-min blocks)';
COMMENT ON COLUMN daily_results.burst_events IS 'Array of significant mood change events';
COMMENT ON COLUMN daily_results.processed_count IS 'Number of spot recordings processed';
COMMENT ON COLUMN daily_results.last_time_block IS 'Last time block processed (format: "HH-MM")';
COMMENT ON COLUMN daily_results.llm_model IS 'LLM model used for analysis (e.g., "groq/openai/gpt-oss-120b")';

-- ============================================================================
-- Migration Complete
-- ============================================================================
