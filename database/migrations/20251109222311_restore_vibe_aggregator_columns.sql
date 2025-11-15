-- Restore vibe_aggregator columns to audio_aggregator table
-- These columns were removed in 003_fix_audio_aggregator_schema.sql
-- but are needed for Vibe Aggregator API to store timeblock prompts

-- Add vibe_aggregator_result column (TEXT type for prompt storage)
ALTER TABLE audio_aggregator
ADD COLUMN IF NOT EXISTS vibe_aggregator_result TEXT;

-- Add vibe_aggregator_processed_at column (timestamp tracking)
ALTER TABLE audio_aggregator
ADD COLUMN IF NOT EXISTS vibe_aggregator_processed_at TIMESTAMP WITH TIME ZONE;

-- Add comments for clarity
COMMENT ON COLUMN audio_aggregator.vibe_aggregator_result IS 'Generated prompt text from Vibe Aggregator API (/generate-timeblock-prompt)';
COMMENT ON COLUMN audio_aggregator.vibe_aggregator_processed_at IS 'Timestamp when Vibe Aggregator processed this record';
