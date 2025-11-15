-- ========================================
-- Timeblock Tables Creation
-- Created: 2025-11-11
-- Purpose: Create 3 tables for timeblock processing
-- ========================================

-- 1. Features table (Output from Features APIs)
CREATE TABLE IF NOT EXISTS timeblock_features (
    device_id TEXT NOT NULL,
    date DATE NOT NULL,
    time_block TEXT NOT NULL,
    vibe_transcriber_result TEXT,
    behavior_extractor_result JSONB,
    emotion_extractor_result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (device_id, date, time_block)
);

-- 2. Aggregators table (Output from Aggregator API)
CREATE TABLE IF NOT EXISTS timeblock_aggregators (
    device_id TEXT NOT NULL,
    date DATE NOT NULL,
    time_block TEXT NOT NULL,
    prompt TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (device_id, date, time_block)
);

-- 3. Results table (Output from Profiler API)
CREATE TABLE IF NOT EXISTS timeblock_results (
    device_id TEXT NOT NULL,
    date DATE NOT NULL,
    time_block TEXT NOT NULL,
    vibe_score DOUBLE PRECISION,
    divergence_index DOUBLE PRECISION,
    summary TEXT,
    behavior TEXT,
    status TEXT DEFAULT 'pending',
    llm_model TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (device_id, date, time_block)
);

-- Create indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_timeblock_features_device_date
ON timeblock_features(device_id, date);

CREATE INDEX IF NOT EXISTS idx_timeblock_results_device_date
ON timeblock_results(device_id, date);

CREATE INDEX IF NOT EXISTS idx_timeblock_results_status
ON timeblock_results(device_id, status);

-- Enable Row Level Security
ALTER TABLE timeblock_features ENABLE ROW LEVEL SECURITY;
ALTER TABLE timeblock_aggregators ENABLE ROW LEVEL SECURITY;
ALTER TABLE timeblock_results ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (to avoid conflicts)
DROP POLICY IF EXISTS "Users can access their own timeblock_features" ON timeblock_features;
DROP POLICY IF EXISTS "Users can access their own timeblock_aggregators" ON timeblock_aggregators;
DROP POLICY IF EXISTS "Users can access their own timeblock_results" ON timeblock_results;

-- RLS Policies: Users can only access data from devices they have access to
CREATE POLICY "Users can access their own timeblock_features"
ON timeblock_features
FOR ALL
USING (
    device_id::uuid IN (
        SELECT device_id FROM user_devices WHERE user_id = auth.uid()
    )
);

CREATE POLICY "Users can access their own timeblock_aggregators"
ON timeblock_aggregators
FOR ALL
USING (
    device_id::uuid IN (
        SELECT device_id FROM user_devices WHERE user_id = auth.uid()
    )
);

CREATE POLICY "Users can access their own timeblock_results"
ON timeblock_results
FOR ALL
USING (
    device_id::uuid IN (
        SELECT device_id FROM user_devices WHERE user_id = auth.uid()
    )
);
