-- Create pipeline_status table for real-time pipeline monitoring
-- Purpose: Track the status of each audio processing pipeline (trace_id based)
-- Date: 2025-11-13

CREATE TABLE pipeline_status (
  trace_id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,

  -- Phase 1-2: Feature Extraction (ASR + SED + SER)
  feature_extraction_status TEXT DEFAULT 'pending',  -- pending/processing/completed/failed
  feature_extraction_started_at TIMESTAMPTZ,
  feature_extraction_completed_at TIMESTAMPTZ,

  -- Phase 3: Aggregation (Prompt Generation)
  aggregation_status TEXT DEFAULT 'pending',
  aggregation_started_at TIMESTAMPTZ,
  aggregation_completed_at TIMESTAMPTZ,

  -- Phase 4-1: Profiling (Spot LLM Analysis)
  profiling_status TEXT DEFAULT 'pending',
  profiling_started_at TIMESTAMPTZ,
  profiling_completed_at TIMESTAMPTZ,

  -- Phase 4-2: Daily Profiling (Cumulative Analysis) - Future implementation
  daily_profiling_status TEXT DEFAULT 'pending',
  daily_profiling_started_at TIMESTAMPTZ,
  daily_profiling_completed_at TIMESTAMPTZ,

  -- Error information
  error_phase TEXT,  -- Which phase failed: feature_extraction/aggregation/profiling/daily_profiling
  error_message TEXT,
  error_occurred_at TIMESTAMPTZ,

  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX idx_pipeline_status_device_id ON pipeline_status(device_id);
CREATE INDEX idx_pipeline_status_recorded_at ON pipeline_status(recorded_at DESC);
CREATE INDEX idx_pipeline_status_updated_at ON pipeline_status(updated_at DESC);
CREATE INDEX idx_pipeline_status_feature_extraction ON pipeline_status(feature_extraction_status);
CREATE INDEX idx_pipeline_status_aggregation ON pipeline_status(aggregation_status);
CREATE INDEX idx_pipeline_status_profiling ON pipeline_status(profiling_status);

-- Disable RLS (internal API only)
ALTER TABLE pipeline_status DISABLE ROW LEVEL SECURITY;

-- Comments
COMMENT ON TABLE pipeline_status IS 'Real-time pipeline status tracking for audio processing workflows';
COMMENT ON COLUMN pipeline_status.trace_id IS 'Unique identifier: {device_id}_{recorded_at}';
COMMENT ON COLUMN pipeline_status.feature_extraction_status IS 'Status of ASR + SED + SER phase';
COMMENT ON COLUMN pipeline_status.aggregation_status IS 'Status of prompt generation phase';
COMMENT ON COLUMN pipeline_status.profiling_status IS 'Status of LLM analysis phase';
COMMENT ON COLUMN pipeline_status.daily_profiling_status IS 'Status of daily cumulative analysis phase (Phase 4-2)';
