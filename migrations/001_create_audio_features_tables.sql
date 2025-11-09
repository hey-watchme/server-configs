-- ============================================================================
-- WatchMe Database Refactoring - Phase 1
-- New Tables Creation for Event-Step Based Architecture
-- Created: 2025-11-09
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. audio_features table
-- Purpose: Store raw analysis results from ASR, SED, SER APIs
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audio_features (
  -- Primary key (follows existing pattern)
  device_id TEXT NOT NULL,
  date DATE NOT NULL,
  time_block TEXT NOT NULL,

  -- Status management
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),

  -- ASR (Automatic Speech Recognition) results
  asr_status TEXT DEFAULT 'pending'
    CHECK (asr_status IN ('pending', 'processing', 'completed', 'failed', 'skipped', 'quota_exceeded')),
  asr_result JSONB,
  asr_transcription TEXT,  -- Direct transcription text for quick access
  asr_processed_at TIMESTAMP WITH TIME ZONE,
  asr_error_message TEXT,

  -- SED (Sound Event Detection) results
  sed_status TEXT DEFAULT 'pending'
    CHECK (sed_status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),
  sed_result JSONB,  -- 527 sound event categories
  sed_processed_at TIMESTAMP WITH TIME ZONE,
  sed_error_message TEXT,

  -- SER (Speech Emotion Recognition) results
  ser_status TEXT DEFAULT 'pending'
    CHECK (ser_status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),
  ser_result JSONB,  -- 8 emotion scores
  ser_processed_at TIMESTAMP WITH TIME ZONE,
  ser_error_message TEXT,

  -- Reference to source
  audio_file_path TEXT,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Primary key constraint
  CONSTRAINT audio_features_pkey PRIMARY KEY (device_id, date, time_block)
);

-- Indexes for audio_features
CREATE INDEX idx_audio_features_status ON audio_features(status)
  WHERE status IN ('pending', 'processing');
CREATE INDEX idx_audio_features_device_date ON audio_features(device_id, date);
CREATE INDEX idx_audio_features_asr_status ON audio_features(asr_status)
  WHERE asr_status IN ('pending', 'processing');
CREATE INDEX idx_audio_features_sed_status ON audio_features(sed_status)
  WHERE sed_status IN ('pending', 'processing');
CREATE INDEX idx_audio_features_ser_status ON audio_features(ser_status)
  WHERE ser_status IN ('pending', 'processing');

-- ----------------------------------------------------------------------------
-- 2. audio_aggregator table
-- Purpose: Store aggregated analysis and prompts for ChatGPT
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audio_aggregator (
  -- Primary key
  device_id TEXT NOT NULL,
  date DATE NOT NULL,
  time_block TEXT NOT NULL,

  -- Status management
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),

  -- Vibe prompt (for ChatGPT analysis)
  vibe_prompt TEXT,
  vibe_prompt_generated_at TIMESTAMP WITH TIME ZONE,

  -- Aggregated behavior data
  behavior_aggregated JSONB,  -- Processed from SED results
  behavior_summary TEXT,       -- Human-readable summary
  behavior_aggregated_at TIMESTAMP WITH TIME ZONE,

  -- Aggregated emotion data
  emotion_aggregated JSONB,   -- Processed from SER results
  emotion_summary TEXT,        -- Human-readable summary
  emotion_aggregated_at TIMESTAMP WITH TIME ZONE,

  -- Combined context for analysis
  context_data JSONB,  -- User profile, time of day, weather, etc.

  -- Error tracking
  error_message TEXT,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Primary key constraint
  CONSTRAINT audio_aggregator_pkey PRIMARY KEY (device_id, date, time_block)
);

-- Indexes for audio_aggregator
CREATE INDEX idx_audio_aggregator_status ON audio_aggregator(status)
  WHERE status IN ('pending', 'processing');
CREATE INDEX idx_audio_aggregator_device_date ON audio_aggregator(device_id, date);

-- ----------------------------------------------------------------------------
-- 3. audio_scorer table
-- Purpose: Store ChatGPT analysis results (final timeblock analysis)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audio_scorer (
  -- Primary key
  device_id TEXT NOT NULL,
  date DATE NOT NULL,
  time_block TEXT NOT NULL,

  -- Status management
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),

  -- Vibe analysis results (from ChatGPT)
  vibe_score DOUBLE PRECISION CHECK (vibe_score >= -100 AND vibe_score <= 100),
  vibe_summary TEXT,
  vibe_analysis JSONB,  -- Full ChatGPT response
  vibe_analyzed_at TIMESTAMP WITH TIME ZONE,

  -- Burst events (emotional highlights)
  burst_events JSONB,

  -- Activity classification
  primary_activity TEXT,
  activity_confidence DOUBLE PRECISION CHECK (activity_confidence >= 0 AND activity_confidence <= 1),

  -- Combined insights
  insights JSONB,
  recommendations JSONB,

  -- Error tracking
  error_message TEXT,
  retry_count INTEGER DEFAULT 0,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Primary key constraint
  CONSTRAINT audio_scorer_pkey PRIMARY KEY (device_id, date, time_block)
);

-- Indexes for audio_scorer
CREATE INDEX idx_audio_scorer_status ON audio_scorer(status);
CREATE INDEX idx_audio_scorer_device_date ON audio_scorer(device_id, date);
CREATE INDEX idx_audio_scorer_vibe_score ON audio_scorer(vibe_score)
  WHERE vibe_score IS NOT NULL;

-- ----------------------------------------------------------------------------
-- 4. summary_daily table
-- Purpose: Store daily cumulative analysis (updated throughout the day)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS summary_daily (
  -- Primary key (note: using UUID for consistency with dashboard_summary)
  device_id UUID NOT NULL,
  date DATE NOT NULL,

  -- Status management
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),

  -- Prompt for daily analysis
  prompt JSONB,  -- Structured prompt with all timeblocks
  prompt_generated_at TIMESTAMP WITH TIME ZONE,

  -- Analysis results
  overall_summary TEXT,
  average_vibe REAL,
  vibe_scores JSONB,  -- Array of 48 scores for the day

  -- Aggregated insights
  hourly_summaries JSONB,
  emotion_trends JSONB,
  behavioral_patterns JSONB,
  burst_events JSONB,

  -- Daily statistics
  processed_count INTEGER DEFAULT 0,
  last_time_block VARCHAR(5),
  last_updated_at TIMESTAMP WITH TIME ZONE,

  -- Error tracking
  error_message TEXT,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Primary key constraint
  CONSTRAINT summary_daily_pkey PRIMARY KEY (device_id, date)
);

-- Indexes for summary_daily
CREATE INDEX idx_summary_daily_status ON summary_daily(status)
  WHERE status IN ('pending', 'processing');
CREATE INDEX idx_summary_daily_device_id ON summary_daily(device_id);
CREATE INDEX idx_summary_daily_date ON summary_daily(date DESC);
CREATE INDEX idx_summary_daily_average_vibe ON summary_daily(average_vibe)
  WHERE average_vibe IS NOT NULL;

-- ----------------------------------------------------------------------------
-- 5. summary_weekly table
-- Purpose: Store weekly aggregated analysis
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS summary_weekly (
  -- Primary key
  device_id UUID NOT NULL,
  week_start_date DATE NOT NULL,  -- Monday of the week

  -- Status management
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),

  -- Analysis prompt
  prompt JSONB,
  prompt_generated_at TIMESTAMP WITH TIME ZONE,

  -- Weekly summary
  overall_summary TEXT,
  average_vibe REAL,

  -- Daily breakdown
  daily_scores JSONB,  -- Array of 7 daily scores
  daily_summaries JSONB,

  -- Weekly trends
  emotion_trends JSONB,
  behavioral_patterns JSONB,
  weekly_highlights JSONB,

  -- Statistics
  days_processed INTEGER DEFAULT 0,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Primary key constraint
  CONSTRAINT summary_weekly_pkey PRIMARY KEY (device_id, week_start_date)
);

-- Indexes for summary_weekly
CREATE INDEX idx_summary_weekly_device_id ON summary_weekly(device_id);
CREATE INDEX idx_summary_weekly_week_start ON summary_weekly(week_start_date DESC);

-- ----------------------------------------------------------------------------
-- 6. summary_monthly table
-- Purpose: Store monthly aggregated analysis
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS summary_monthly (
  -- Primary key
  device_id UUID NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),

  -- Status management
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'processing', 'completed', 'failed')),

  -- Analysis prompt
  prompt JSONB,
  prompt_generated_at TIMESTAMP WITH TIME ZONE,

  -- Monthly summary
  overall_summary TEXT,
  average_vibe REAL,

  -- Weekly breakdown
  weekly_scores JSONB,  -- Array of 4-5 weekly scores
  weekly_summaries JSONB,

  -- Monthly trends
  emotion_trends JSONB,
  behavioral_patterns JSONB,
  monthly_highlights JSONB,

  -- Statistics
  weeks_processed INTEGER DEFAULT 0,
  days_processed INTEGER DEFAULT 0,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Primary key constraint
  CONSTRAINT summary_monthly_pkey PRIMARY KEY (device_id, year, month)
);

-- Indexes for summary_monthly
CREATE INDEX idx_summary_monthly_device_id ON summary_monthly(device_id);
CREATE INDEX idx_summary_monthly_year_month ON summary_monthly(year DESC, month DESC);

-- ----------------------------------------------------------------------------
-- 7. Create update trigger function if not exists
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- 8. Apply update triggers to all tables
-- ----------------------------------------------------------------------------
CREATE TRIGGER update_audio_features_updated_at
  BEFORE UPDATE ON audio_features
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_audio_aggregator_updated_at
  BEFORE UPDATE ON audio_aggregator
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_audio_scorer_updated_at
  BEFORE UPDATE ON audio_scorer
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_summary_daily_updated_at
  BEFORE UPDATE ON summary_daily
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_summary_weekly_updated_at
  BEFORE UPDATE ON summary_weekly
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_summary_monthly_updated_at
  BEFORE UPDATE ON summary_monthly
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 9. Add comments for documentation
-- ----------------------------------------------------------------------------
COMMENT ON TABLE audio_features IS
  'Stores raw analysis results from ASR, SED, and SER APIs for each timeblock';

COMMENT ON TABLE audio_aggregator IS
  'Stores aggregated analysis results and prompts for ChatGPT processing';

COMMENT ON TABLE audio_scorer IS
  'Stores final ChatGPT analysis results for each timeblock';

COMMENT ON TABLE summary_daily IS
  'Stores daily cumulative analysis, updated throughout the day as new timeblocks are processed';

COMMENT ON TABLE summary_weekly IS
  'Stores weekly aggregated analysis based on daily summaries';

COMMENT ON TABLE summary_monthly IS
  'Stores monthly aggregated analysis based on weekly summaries';

-- ----------------------------------------------------------------------------
-- End of migration
-- ----------------------------------------------------------------------------