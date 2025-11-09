-- Fix audio_aggregator table schema
-- Remove time_block from Primary Key (1日1レコード、not 30分単位)
-- Remove unnecessary columns

-- Step 0: Delete existing test data (confirmed by user)
DELETE FROM audio_aggregator;

-- Step 1: Drop existing primary key constraint
ALTER TABLE audio_aggregator DROP CONSTRAINT IF EXISTS audio_aggregator_pkey;

-- Step 2: Drop time_block column (不要)
ALTER TABLE audio_aggregator DROP COLUMN IF EXISTS time_block;

-- Step 3: Drop unnecessary columns
ALTER TABLE audio_aggregator DROP COLUMN IF EXISTS behavior_aggregator_summary;
ALTER TABLE audio_aggregator DROP COLUMN IF EXISTS emotion_aggregator_summary;
ALTER TABLE audio_aggregator DROP COLUMN IF EXISTS vibe_aggregator_result;
ALTER TABLE audio_aggregator DROP COLUMN IF EXISTS vibe_aggregator_processed_at;
ALTER TABLE audio_aggregator DROP COLUMN IF EXISTS context_data;
ALTER TABLE audio_aggregator DROP COLUMN IF EXISTS status;
ALTER TABLE audio_aggregator DROP COLUMN IF EXISTS error_message;

-- Step 4: Add new primary key (device_id, date) - 1日1レコード
ALTER TABLE audio_aggregator ADD PRIMARY KEY (device_id, date);

-- Verify the new structure
COMMENT ON TABLE audio_aggregator IS 'Aggregator API results - 1 record per day, updated every time_block';
COMMENT ON COLUMN audio_aggregator.behavior_aggregator_result IS 'time_blocks JSONB data from Behavior Aggregator';
COMMENT ON COLUMN audio_aggregator.emotion_aggregator_result IS 'Emotion aggregation result JSONB';
