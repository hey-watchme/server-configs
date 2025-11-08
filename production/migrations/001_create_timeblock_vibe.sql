-- =============================================================================
-- Migration: 001_create_timeblock_vibe
-- Description: Create timeblock_vibe table for unified Vibe processing
-- Author: WatchMe Team
-- Date: 2025-11-09
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Create trigger function for updated_at
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 2. Create timeblock_vibe table
-- -----------------------------------------------------------------------------
CREATE TABLE timeblock_vibe (
  device_id UUID NOT NULL,
  date DATE NOT NULL,
  time_block TEXT NOT NULL,

  -- ========================================
  -- ステータス管理（処理の進行状態）
  -- ========================================
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN (
      'pending',        -- 未処理（音声ファイル待ち）
      'transcribing',   -- Step 1実行中
      'transcribed',    -- Step 1完了、Step 2待ち
      'generating',     -- Step 2実行中（プロンプト生成）
      'prompt_ready',   -- Step 2完了、Step 3待ち
      'scoring',        -- Step 3実行中（ChatGPT分析）
      'completed',      -- Step 3完了（全ステップ完了）
      'failed',         -- 失敗
      'skipped'         -- 夜間スキップ（23:00-05:59）
    )),

  -- 失敗情報（status='failed'の場合のみ）
  failure_reason TEXT
    CHECK (failure_reason IN ('quota_exceeded', 'timeout', 'api_error', 'network_error', NULL)),
  error_message TEXT,

  -- ========================================
  -- Step 1: Vibe Transcriber の結果（素材）
  -- ========================================
  transcription TEXT,
  transcribed_at TIMESTAMP WITH TIME ZONE,

  -- ========================================
  -- Step 2: Vibe Aggregator の結果（素材、保存必須）
  -- ========================================
  prompt TEXT,  -- ChatGPT用プロンプト（検証・デバッグで頻繁に使用）
  prompt_generated_at TIMESTAMP WITH TIME ZONE,

  -- ========================================
  -- Step 3: Vibe Scorer の結果（表示用）
  -- ========================================
  vibe_score INTEGER CHECK (vibe_score BETWEEN -100 AND 100),
  summary TEXT,  -- タイムブロックのコメント
  burst_events JSONB,  -- 感情変化のイベント
  analysis_result JSONB,  -- その他の分析結果
  analyzed_at TIMESTAMP WITH TIME ZONE,

  -- ========================================
  -- メタデータ
  -- ========================================
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  PRIMARY KEY (device_id, date, time_block),

  -- ========================================
  -- データ整合性制約
  -- ========================================

  -- completedの場合、全てのデータが揃っている必要がある
  CONSTRAINT check_completed_has_all_data CHECK (
    (status = 'completed' AND
     transcription IS NOT NULL AND
     prompt IS NOT NULL AND
     vibe_score IS NOT NULL AND
     summary IS NOT NULL) OR
    (status != 'completed')
  ),

  -- failedの場合、failure_reasonが必要
  CONSTRAINT check_failed_has_reason CHECK (
    (status = 'failed' AND failure_reason IS NOT NULL) OR
    (status != 'failed')
  ),

  -- skippedの場合、分析結果はNULL
  CONSTRAINT check_skipped_no_analysis CHECK (
    (status = 'skipped' AND vibe_score IS NULL AND prompt IS NULL) OR
    (status != 'skipped')
  )
);

-- -----------------------------------------------------------------------------
-- 3. Create indexes
-- -----------------------------------------------------------------------------
CREATE INDEX idx_timeblock_vibe_device_date
  ON timeblock_vibe(device_id, date);

CREATE INDEX idx_timeblock_vibe_status
  ON timeblock_vibe(status)
  WHERE status IN ('pending', 'transcribed', 'prompt_ready');  -- 処理待ちのものだけ

-- -----------------------------------------------------------------------------
-- 4. Create trigger for updated_at
-- -----------------------------------------------------------------------------
CREATE TRIGGER update_timeblock_vibe_updated_at
  BEFORE UPDATE ON timeblock_vibe
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 5. Add comments for documentation
-- -----------------------------------------------------------------------------
COMMENT ON TABLE timeblock_vibe IS
  '気分（Vibe）分析の全3ステップを統合管理するテーブル
   - Step 1: Transcriber（文字起こし）
   - Step 2: Aggregator（プロンプト生成）
   - Step 3: Scorer（ChatGPT分析）';

COMMENT ON COLUMN timeblock_vibe.status IS
  '処理ステータス：
   pending → transcribing → transcribed → generating → prompt_ready → scoring → completed
   または failed / skipped';

COMMENT ON COLUMN timeblock_vibe.transcription IS
  'Step 1の出力：Azure Speech APIによる文字起こし（素材データ）';

COMMENT ON COLUMN timeblock_vibe.prompt IS
  'Step 2の出力：ChatGPT用プロンプト（検証・デバッグで頻繁に使用、保存必須）';

COMMENT ON COLUMN timeblock_vibe.vibe_score IS
  'Step 3の出力：気分スコア（-100〜100、アプリ表示用）';

COMMENT ON COLUMN timeblock_vibe.summary IS
  'Step 3の出力：タイムブロックのコメント（アプリ表示用）';

COMMENT ON COLUMN timeblock_vibe.burst_events IS
  'Step 3の出力：感情変化イベント（アプリ表示用）';

-- =============================================================================
-- Migration Complete
-- =============================================================================
