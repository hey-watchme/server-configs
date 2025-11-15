-- WatchMe Database Schema (Current State)
-- Last Updated: 2025-11-13 (Evening)
--
-- This file contains the current database schema for all main tables.
-- Update this file whenever schema changes are made.
--
-- Usage: Claude references this file to understand the current database structure.
-- Update command: Ask Claude "スキーマを更新してください" or "current_schema.sql を更新して"
--
-- Important Data Flow:
--   spot_results (1 day = multiple records) → daily_aggregators → daily_results (1 day = 1 record)
--   daily_results (7 days) → weekly_aggregators → weekly_results (1 week = 1 record)
--   daily_results (30 days) → monthly_aggregators → monthly_results (1 month = 1 record)

-- ============================================================================
-- Core Tables
-- ============================================================================

-- audio_files: S3にアップロードされた音声ファイルのメタデータ
CREATE TABLE audio_files (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  file_path TEXT NOT NULL,
  transcriptions_status TEXT NOT NULL,
  created_at TIMESTAMPTZ,
  behavior_features_status TEXT NOT NULL,
  emotion_features_status TEXT NOT NULL,
  file_status TEXT NOT NULL,
  PRIMARY KEY (device_id, recorded_at)
);

-- devices: デバイス情報（タイムゾーン含む）
CREATE TABLE devices (
  device_id UUID NOT NULL,
  device_type TEXT,
  registered_at TIMESTAMP WITHOUT TIME ZONE,
  status TEXT,
  subject_id UUID,
  timezone TEXT,
  PRIMARY KEY (device_id)
);

-- users: ユーザー情報
CREATE TABLE users (
  user_id UUID NOT NULL,
  name TEXT,
  email TEXT,
  created_at TIMESTAMP WITHOUT TIME ZONE,
  newsletter_subscription BOOLEAN,
  updated_at TIMESTAMPTZ,
  status TEXT,
  subscription_plan TEXT,
  avatar_url TEXT,
  apns_token TEXT,
  PRIMARY KEY (user_id)
);

-- ============================================================================
-- Feature Extraction Layer (Layer 1)
-- ============================================================================

-- spot_features: 特徴抽出結果（ASR + SED + SER）
CREATE TABLE spot_features (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  vibe_transcriber_result TEXT,
  behavior_extractor_result JSONB,
  emotion_extractor_result JSONB,
  created_at TIMESTAMPTZ,
  behavior_extractor_status TEXT,
  behavior_extractor_processed_at TIMESTAMPTZ,
  emotion_extractor_status TEXT,
  emotion_extractor_processed_at TIMESTAMPTZ,
  vibe_transcriber_status TEXT,
  vibe_transcriber_processed_at TIMESTAMPTZ,
  PRIMARY KEY (device_id, recorded_at)
);

-- ============================================================================
-- Aggregation Layer (Layer 2)
-- ============================================================================

-- spot_aggregators: 統合プロンプト（LLM分析用）
CREATE TABLE spot_aggregators (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  prompt TEXT NOT NULL,
  context_data JSONB,
  created_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (device_id, recorded_at)
);

-- ============================================================================
-- Profiling Layer (Layer 3)
-- ============================================================================

-- spot_results: スポット分析結果（1回の録音ごと）
CREATE TABLE spot_results (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  vibe_score DOUBLE PRECISION,
  profile_result JSONB NOT NULL,
  created_at TIMESTAMPTZ,
  llm_model TEXT,
  summary TEXT,           -- Dashboard display summary
  behavior TEXT,          -- Detected behavior pattern
  PRIMARY KEY (device_id, recorded_at)
);

-- daily_aggregators: 日次統合プロンプト (Layer 2)
CREATE TABLE daily_aggregators (
  device_id TEXT NOT NULL,
  date DATE NOT NULL,
  prompt TEXT NOT NULL,
  context_data JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (device_id, date)
);

-- daily_results: 日次分析結果 (Layer 3, 旧 summary_daily)
CREATE TABLE daily_results (
  device_id TEXT NOT NULL,
  date DATE NOT NULL,
  status TEXT NOT NULL,
  prompt JSONB,
  prompt_generated_at TIMESTAMPTZ,
  overall_summary TEXT,
  average_vibe REAL,
  vibe_scores JSONB,
  hourly_summaries JSONB,
  emotion_trends JSONB,
  behavioral_patterns JSONB,
  burst_events JSONB,
  processed_count INTEGER,
  last_time_block TEXT,
  last_updated_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  summary TEXT,           -- NEW: Dashboard display summary (Japanese)
  behavior TEXT,          -- NEW: Key behavior patterns (comma-separated)
  llm_model TEXT,         -- NEW: LLM model used
  PRIMARY KEY (device_id, date)
);

-- weekly_aggregators: 週次統合プロンプト (Layer 2)
CREATE TABLE weekly_aggregators (
  device_id TEXT NOT NULL,
  week_start_date DATE NOT NULL,
  week_end_date DATE NOT NULL,
  prompt TEXT NOT NULL,
  context_data JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (device_id, week_start_date)
);

-- weekly_results: 週次分析結果 (Layer 3, 旧 summary_weekly)
CREATE TABLE weekly_results (
  device_id TEXT NOT NULL,
  week_start_date DATE NOT NULL,
  status TEXT NOT NULL,
  prompt JSONB,
  prompt_generated_at TIMESTAMPTZ,
  overall_summary TEXT,
  average_vibe REAL,
  daily_scores JSONB,
  daily_summaries JSONB,
  emotion_trends JSONB,
  behavioral_patterns JSONB,
  weekly_highlights JSONB,
  days_processed INTEGER,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  summary TEXT,           -- NEW
  behavior TEXT,          -- NEW
  llm_model TEXT,         -- NEW
  PRIMARY KEY (device_id, week_start_date)
);

-- monthly_aggregators: 月次統合プロンプト (Layer 2)
CREATE TABLE monthly_aggregators (
  device_id TEXT NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  prompt TEXT NOT NULL,
  context_data JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (device_id, year, month)
);

-- monthly_results: 月次分析結果 (Layer 3, 旧 summary_monthly)
CREATE TABLE monthly_results (
  device_id TEXT NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  status TEXT NOT NULL,
  prompt JSONB,
  prompt_generated_at TIMESTAMPTZ,
  overall_summary TEXT,
  average_vibe REAL,
  weekly_scores JSONB,
  weekly_summaries JSONB,
  emotion_trends JSONB,
  behavioral_patterns JSONB,
  monthly_highlights JSONB,
  weeks_processed INTEGER,
  days_processed INTEGER,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  summary TEXT,           -- NEW
  behavior TEXT,          -- NEW
  llm_model TEXT,         -- NEW
  PRIMARY KEY (device_id, year, month)
);

-- ============================================================================
-- Notes
-- ============================================================================

-- RLS (Row Level Security):
-- - spot_features, spot_aggregators, spot_results: DISABLED (internal API only)
-- - daily_aggregators, weekly_aggregators, monthly_aggregators: DISABLED (internal API only)
-- - daily_results, weekly_results, monthly_results: ENABLED (user-facing, 旧 summary_*)
-- - devices, users: ENABLED (user-facing)

-- Timezone Handling:
-- - All timestamps stored in UTC (TIMESTAMPTZ)
-- - Local time conversion uses devices.timezone
-- - Display layer converts UTC -> Local time

-- Data Flow:
-- 1. audio_files (S3 upload)
-- 2. spot_features (ASR + SED + SER extraction)
-- 3. spot_aggregators (prompt generation)
-- 4. spot_results (LLM profiling)
-- 5. Cumulative Analysis:
--    - spot_results (multiple per day) → daily_aggregators → daily_results (1 per day)
--    - daily_results (7 days) → weekly_aggregators → weekly_results (1 per week)
--    - daily_results (30 days) → monthly_aggregators → monthly_results (1 per month)
