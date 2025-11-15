-- Migration: Rename summary_* tables to *_results and create *_aggregators tables
-- Date: 2025-11-13
-- Purpose: Unify naming convention across all layers
--
-- Data Flow:
--   spot_results (1 day = multiple records)
--     ↓ aggregate
--   daily_aggregators.prompt (1 day = 1 prompt)
--     ↓ LLM analysis
--   daily_results (1 day = 1 result)
--
-- Changes:
-- 1. Rename summary_daily -> daily_results (preserve existing schema)
-- 2. Rename summary_weekly -> weekly_results (preserve existing schema)
-- 3. Rename summary_monthly -> monthly_results (preserve existing schema)
-- 4. Create daily_aggregators (Layer 2 - Aggregation)
-- 5. Create weekly_aggregators (Layer 2 - Aggregation)
-- 6. Create monthly_aggregators (Layer 2 - Aggregation)

-- ============================================================================
-- Step 1: Rename summary_* tables to *_results (Layer 3 - Profiling)
-- ============================================================================

-- Rename summary_daily to daily_results
ALTER TABLE summary_daily RENAME TO daily_results;

-- Rename summary_weekly to weekly_results
ALTER TABLE summary_weekly RENAME TO weekly_results;

-- Rename summary_monthly to monthly_results
ALTER TABLE summary_monthly RENAME TO monthly_results;

-- ============================================================================
-- Step 2: Create daily_aggregators (Layer 2 - Aggregation)
-- ============================================================================

CREATE TABLE daily_aggregators (
  device_id TEXT NOT NULL,
  date DATE NOT NULL,                -- Local date (based on device timezone)
  prompt TEXT NOT NULL,               -- LLM analysis prompt (aggregated from spot_results)
  context_data JSONB,                 -- Metadata (timezone, spot_count, etc.)
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (device_id, date)
);

-- Disable RLS for internal API use
ALTER TABLE daily_aggregators DISABLE ROW LEVEL SECURITY;

COMMENT ON TABLE daily_aggregators IS 'Layer 2 (Aggregation): Daily aggregated prompts for LLM analysis';
COMMENT ON COLUMN daily_aggregators.prompt IS 'LLM analysis prompt generated from spot_results (1 day)';
COMMENT ON COLUMN daily_aggregators.date IS 'Local date based on device timezone';
COMMENT ON COLUMN daily_aggregators.context_data IS 'Metadata: timezone, spot_count, average_vibe_score, etc.';

-- ============================================================================
-- Step 3: Create weekly_aggregators (Layer 2 - Aggregation)
-- ============================================================================

CREATE TABLE weekly_aggregators (
  device_id TEXT NOT NULL,
  week_start_date DATE NOT NULL,      -- Week start (Monday, local date)
  week_end_date DATE NOT NULL,        -- Week end (Sunday, local date)
  prompt TEXT NOT NULL,               -- LLM analysis prompt (aggregated from daily_results)
  context_data JSONB,                 -- Metadata (timezone, active_days, etc.)
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (device_id, week_start_date)
);

-- Disable RLS for internal API use
ALTER TABLE weekly_aggregators DISABLE ROW LEVEL SECURITY;

COMMENT ON TABLE weekly_aggregators IS 'Layer 2 (Aggregation): Weekly aggregated prompts for LLM analysis';
COMMENT ON COLUMN weekly_aggregators.prompt IS 'LLM analysis prompt generated from daily_results (7 days)';
COMMENT ON COLUMN weekly_aggregators.week_start_date IS 'Week start date (Monday, local date)';
COMMENT ON COLUMN weekly_aggregators.week_end_date IS 'Week end date (Sunday, local date)';

-- ============================================================================
-- Step 4: Create monthly_aggregators (Layer 2 - Aggregation)
-- ============================================================================

CREATE TABLE monthly_aggregators (
  device_id TEXT NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,             -- 1-12
  prompt TEXT NOT NULL,               -- LLM analysis prompt (aggregated from daily_results)
  context_data JSONB,                 -- Metadata (timezone, active_days, etc.)
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (device_id, year, month)
);

-- Disable RLS for internal API use
ALTER TABLE monthly_aggregators DISABLE ROW LEVEL SECURITY;

COMMENT ON TABLE monthly_aggregators IS 'Layer 2 (Aggregation): Monthly aggregated prompts for LLM analysis';
COMMENT ON COLUMN monthly_aggregators.prompt IS 'LLM analysis prompt generated from daily_results (30 days)';
COMMENT ON COLUMN monthly_aggregators.year IS 'Year (e.g., 2025)';
COMMENT ON COLUMN monthly_aggregators.month IS 'Month (1-12)';

-- ============================================================================
-- Step 5: Update daily_results schema (minimal changes)
-- ============================================================================

-- Keep existing schema mostly intact
-- Only update device_id type for consistency with spot_results
ALTER TABLE daily_results ALTER COLUMN device_id TYPE TEXT;

-- Add new columns for future use (optional, won't break existing data)
ALTER TABLE daily_results ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE daily_results ADD COLUMN IF NOT EXISTS behavior TEXT;
ALTER TABLE daily_results ADD COLUMN IF NOT EXISTS llm_model TEXT;

COMMENT ON TABLE daily_results IS 'Layer 3 (Profiling): Daily cumulative analysis results (1 day = 1 record)';

-- ============================================================================
-- Step 6: Update weekly_results schema (minimal changes)
-- ============================================================================

ALTER TABLE weekly_results ALTER COLUMN device_id TYPE TEXT;

ALTER TABLE weekly_results ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE weekly_results ADD COLUMN IF NOT EXISTS behavior TEXT;
ALTER TABLE weekly_results ADD COLUMN IF NOT EXISTS llm_model TEXT;

COMMENT ON TABLE weekly_results IS 'Layer 3 (Profiling): Weekly cumulative analysis results (1 week = 1 record)';

-- ============================================================================
-- Step 7: Update monthly_results schema (minimal changes)
-- ============================================================================

ALTER TABLE monthly_results ALTER COLUMN device_id TYPE TEXT;

ALTER TABLE monthly_results ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE monthly_results ADD COLUMN IF NOT EXISTS behavior TEXT;
ALTER TABLE monthly_results ADD COLUMN IF NOT EXISTS llm_model TEXT;

COMMENT ON TABLE monthly_results IS 'Layer 3 (Profiling): Monthly cumulative analysis results (1 month = 1 record)';

-- ============================================================================
-- Migration Complete
-- ============================================================================
