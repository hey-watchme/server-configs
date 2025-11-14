-- ============================================================================
-- WatchMe Database Refactoring - Phase 2
-- Rename columns for naming consistency with API endpoints
-- Created: 2025-11-09
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. audio_features table - Rename columns
-- ----------------------------------------------------------------------------

-- ASR (Automatic Speech Recognition) → Transcriber
ALTER TABLE audio_features RENAME COLUMN asr_status TO transcriber_status;
ALTER TABLE audio_features RENAME COLUMN asr_result TO transcriber_result;
ALTER TABLE audio_features RENAME COLUMN asr_processed_at TO transcriber_processed_at;
ALTER TABLE audio_features RENAME COLUMN asr_error_message TO transcriber_error_message;

-- Remove asr_transcription (merged into transcriber_result)
ALTER TABLE audio_features DROP COLUMN IF EXISTS asr_transcription;

-- Drop view temporarily to allow column type change
DROP VIEW IF EXISTS v_processing_pipeline;

-- Change transcriber_result type from JSONB to TEXT (simple transcription text)
ALTER TABLE audio_features ALTER COLUMN transcriber_result TYPE TEXT;

-- SED (Sound Event Detection) → Behavior Extractor
ALTER TABLE audio_features RENAME COLUMN sed_status TO behavior_extractor_status;
ALTER TABLE audio_features RENAME COLUMN sed_result TO behavior_extractor_result;
ALTER TABLE audio_features RENAME COLUMN sed_processed_at TO behavior_extractor_processed_at;
ALTER TABLE audio_features RENAME COLUMN sed_error_message TO behavior_extractor_error_message;

-- SER (Speech Emotion Recognition) → Emotion Extractor
ALTER TABLE audio_features RENAME COLUMN ser_status TO emotion_extractor_status;
ALTER TABLE audio_features RENAME COLUMN ser_result TO emotion_extractor_result;
ALTER TABLE audio_features RENAME COLUMN ser_processed_at TO emotion_extractor_processed_at;
ALTER TABLE audio_features RENAME COLUMN ser_error_message TO emotion_extractor_error_message;

-- Update indexes
DROP INDEX IF EXISTS idx_audio_features_asr_status;
DROP INDEX IF EXISTS idx_audio_features_sed_status;
DROP INDEX IF EXISTS idx_audio_features_ser_status;

CREATE INDEX idx_audio_features_transcriber_status ON audio_features(transcriber_status)
  WHERE transcriber_status IN ('pending', 'processing');
CREATE INDEX idx_audio_features_behavior_extractor_status ON audio_features(behavior_extractor_status)
  WHERE behavior_extractor_status IN ('pending', 'processing');
CREATE INDEX idx_audio_features_emotion_extractor_status ON audio_features(emotion_extractor_status)
  WHERE emotion_extractor_status IN ('pending', 'processing');

-- ----------------------------------------------------------------------------
-- 2. audio_aggregator table - Rename columns
-- ----------------------------------------------------------------------------

-- vibe_prompt → vibe_aggregator_result (consistent naming)
ALTER TABLE audio_aggregator RENAME COLUMN vibe_prompt TO vibe_aggregator_result;
ALTER TABLE audio_aggregator RENAME COLUMN vibe_prompt_generated_at TO vibe_aggregator_processed_at;

-- behavior_aggregated → behavior_aggregator_result
ALTER TABLE audio_aggregator RENAME COLUMN behavior_aggregated TO behavior_aggregator_result;
ALTER TABLE audio_aggregator RENAME COLUMN behavior_summary TO behavior_aggregator_summary;
ALTER TABLE audio_aggregator RENAME COLUMN behavior_aggregated_at TO behavior_aggregator_processed_at;

-- emotion_aggregated → emotion_aggregator_result
ALTER TABLE audio_aggregator RENAME COLUMN emotion_aggregated TO emotion_aggregator_result;
ALTER TABLE audio_aggregator RENAME COLUMN emotion_summary TO emotion_aggregator_summary;
ALTER TABLE audio_aggregator RENAME COLUMN emotion_aggregated_at TO emotion_aggregator_processed_at;

-- ----------------------------------------------------------------------------
-- 3. audio_scorer table - Rename/Add columns
-- ----------------------------------------------------------------------------

-- Add vibe_behavior column (behavior classification result)
ALTER TABLE audio_scorer ADD COLUMN IF NOT EXISTS vibe_behavior TEXT;

-- Rename vibe_analysis → vibe_scorer_result
ALTER TABLE audio_scorer RENAME COLUMN vibe_analysis TO vibe_scorer_result;

-- Keep vibe_score and vibe_summary as separate columns (frequently accessed)
-- vibe_score (DOUBLE PRECISION) - already exists
-- vibe_summary (TEXT) - already exists

-- Remove redundant columns from previous design
ALTER TABLE audio_scorer DROP COLUMN IF EXISTS burst_events;
ALTER TABLE audio_scorer DROP COLUMN IF EXISTS primary_activity;
ALTER TABLE audio_scorer DROP COLUMN IF EXISTS activity_confidence;
ALTER TABLE audio_scorer DROP COLUMN IF EXISTS insights;
ALTER TABLE audio_scorer DROP COLUMN IF EXISTS recommendations;

-- ----------------------------------------------------------------------------
-- 4. Update table comments
-- ----------------------------------------------------------------------------

COMMENT ON TABLE audio_features IS
  'Stores raw analysis results from Transcriber, Behavior Extractor, and Emotion Extractor APIs for each timeblock';

COMMENT ON COLUMN audio_features.transcriber_result IS
  'Transcription text from Vibe Transcriber API (TEXT format)';

COMMENT ON COLUMN audio_features.behavior_extractor_result IS
  'Sound event detection results from Behavior Features API (JSONB format, 527 categories)';

COMMENT ON COLUMN audio_features.emotion_extractor_result IS
  'Emotion recognition results from Emotion Features API (JSONB format, 8 emotions)';

COMMENT ON TABLE audio_aggregator IS
  'Stores aggregated analysis results and prompts from Aggregator APIs';

COMMENT ON COLUMN audio_aggregator.vibe_aggregator_result IS
  'Generated prompt for ChatGPT analysis (TEXT format)';

COMMENT ON TABLE audio_scorer IS
  'Stores final ChatGPT analysis results from Vibe Scorer API for each timeblock';

COMMENT ON COLUMN audio_scorer.vibe_scorer_result IS
  'Full ChatGPT response with detailed analysis (JSONB format)';

-- ----------------------------------------------------------------------------
-- End of migration
-- ----------------------------------------------------------------------------

-- Verification query
SELECT
  'audio_features' as table_name,
  column_name,
  data_type
FROM information_schema.columns
WHERE table_name = 'audio_features'
  AND column_name LIKE '%transcriber%'
     OR column_name LIKE '%behavior_extractor%'
     OR column_name LIKE '%emotion_extractor%'
ORDER BY ordinal_position;
